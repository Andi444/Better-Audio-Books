"""Better Audio Books — shared desktop backend, Python 3.12+."""
from __future__ import annotations
import asyncio
from contextlib import contextmanager
import hashlib
import html
import json
import logging
import os
from pathlib import Path
import re
import secrets
import sqlite3
import subprocess
import sys
import threading
import time
import unicodedata
import uuid
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
from platform_support import data_directory, capabilities

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'online_packages'))
sys.path.insert(0, str(ROOT / 'offline_packages'))
DATA = data_directory()
CACHE = DATA / 'audio'
TOKEN = secrets.token_urlsafe(32)
SLOTS = threading.BoundedSemaphore(2)
CACHE_LOCKS: dict[str, threading.Lock] = {}
LOCK = threading.Lock()
MAX_TEXT = 1_000_000
last_activity = time.monotonic()

STYLES = [
    ('Original', 0, 0), ('Varm', -15, -4), ('Lugn', -5, -14),
    ('Djup', -30, -5), ('Ljus', 25, 0), ('Mjuk', -10, -8),
    ('Tydlig', 5, -6), ('Livlig', 15, 8), ('Eftertänksam', -20, -12),
    ('Lättsam', 10, 4), ('Mörk', -25, 0), ('Luftig', 20, -5),
    ('Stadig', -10, 2), ('Rofylld', -15, -16), ('Pigg', 25, 10),
    ('Berättande', -5, -5), ('Långsam', 0, -20), ('Snabb', 0, 15),
    ('Ljus och lugn', 30, -12), ('Djup och rask', -30, 8),
]
VOICES = [dict(id=f'{gender}-{i+1:02}', name=f'{base} · {name}', style=name,
               gender=gender, base=base, mode='offline', engine=f'piper-sv-{base.lower()}', pitch=f'{pitch:+}Hz', rate=f'{rate:+}%')
          for gender, base in [('male', 'NST'), ('female', 'Alma')]
          for i, (name, pitch, rate) in enumerate(STYLES)]
VOICES += [dict(id=f'online-{gender}-{i+1:02}', name=f'{base} · {name}', style=name,
                gender=gender, base=base, mode='online', engine=f'sv-SE-{base}Neural', pitch=f'{pitch:+}Hz', rate=f'{rate:+}%')
           for gender, base in [('male', 'Mattias'), ('female', 'Sofie')]
           for i, (name, pitch, rate) in enumerate(STYLES)]
VOICE_MAP = {v['id']: v for v in VOICES}

def initialize():
    CACHE.mkdir(parents=True, exist_ok=True)
    with database() as db:
        db.execute('CREATE TABLE IF NOT EXISTS books (id TEXT PRIMARY KEY, title TEXT NOT NULL, text TEXT NOT NULL, position INTEGER NOT NULL DEFAULT 0, voice TEXT NOT NULL, updated REAL NOT NULL)')
        db.execute('CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), value TEXT NOT NULL)')

@contextmanager
def database():
    db = sqlite3.connect(DATA / 'library.sqlite3', timeout=15)
    db.row_factory = sqlite3.Row
    try:
        with db:
            yield db
    finally:
        db.close()

def compact(value):
    return ''.join(c for c in unicodedata.normalize('NFKC', html.unescape(value)).casefold() if c.isalnum())

def align_boundaries(text, events):
    """Map source word indices to real synthesis timestamps, including split compounds."""
    words = re.findall(r'\S+', text)
    normalized, owners = '', []
    for i, word in enumerate(words):
        part = compact(word)
        normalized += part
        owners.extend([i] * len(part))
    cursor = 0
    result = []
    for event in events:
        part = compact(event['text'])
        if not part:
            continue
        at = normalized.find(part, cursor)
        if at < 0:
            # Do not invent word timings if the service changes its text format.
            raise ValueError('Rösttjänstens ordmarkering kunde inte kopplas till texten. Prova att skriva ut siffror eller förkortningar med bokstäver.')
        end = at + len(part)
        result.append(dict(start=event['offset']/10_000_000, duration=event['duration']/10_000_000,
                           word=owners[at], lastWord=owners[end-1]))
        cursor = end
    if not result:
        raise ValueError('Ingen ordmarkering kom från rösttjänsten. Försök igen.')
    return result


async def synthesize_online(text, voice):
    import edge_tts
    audio = bytearray()
    events = []
    speaker = edge_tts.Communicate(text, voice['engine'], pitch=voice['pitch'], rate=voice['rate'],
                                  boundary='WordBoundary', connect_timeout=12, receive_timeout=45)
    async for event in speaker.stream():
        if event['type'] == 'audio':
            audio.extend(event['data'])
        elif event['type'] == 'WordBoundary':
            events.append(event)
    if len(audio) < 100:
        raise ValueError('Rösttjänsten returnerade inget ljud.')
    return bytes(audio), align_boundaries(text, events)

def get_speech(text, voice_id):
    if not isinstance(text, str) or not text.strip() or len(text) > 3500:
        raise ValueError('Textavsnittet måste vara mellan 1 och 3 500 tecken.')
    if voice_id not in VOICE_MAP:
        raise ValueError('Välj en röst i listan.')
    voice = VOICE_MAP[voice_id]
    key = hashlib.sha256(json.dumps([5, text, voice], ensure_ascii=False).encode()).hexdigest()
    extension = 'mp3' if voice['mode'] == 'online' else 'wav'
    with LOCK:
        mutex = CACHE_LOCKS.setdefault(key, threading.Lock())
    with mutex:
        audio_path, meta_path = CACHE / f'{key}.{extension}', CACHE / f'{key}.json'
        if meta_path.exists() and audio_path.exists():
            try:
                timings = json.loads(meta_path.read_text(encoding='utf-8'))
                return dict(audio=f'/audio/{key}.{extension}', timings=timings, cached=True)
            except (ValueError, OSError):
                pass
        with SLOTS:
            if voice['mode'] == 'online':
                try:
                    audio, timings = asyncio.run(asyncio.wait_for(synthesize_online(text, voice), timeout=75))
                except ValueError:
                    raise
                except Exception as exc:
                    logging.exception('Online speech failed')
                    raise ValueError('Onlinerösten kunde inte nås. Kontrollera internetanslutningen eller välj Offline i röstpanelen. Din läsposition finns kvar.') from exc
            else:
                from offline_speech import synthesize
                audio, timings = synthesize(text, voice, CACHE)
        audio_path.with_suffix('.tmp').write_bytes(audio)
        audio_path.with_suffix('.tmp').replace(audio_path)
        meta_path.with_suffix('.tmp').write_text(json.dumps(timings), encoding='utf-8')
        meta_path.with_suffix('.tmp').replace(meta_path)
        return dict(audio=f'/audio/{key}.{extension}', timings=timings, cached=False)

class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def respond(self, value, code=200):
        data = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        global last_activity
        supplied = self.headers.get('X-BAB-Token', '') or parse_qs(urlsplit(self.path).query).get('token', [''])[0]
        if not secrets.compare_digest(supplied, TOKEN):
            self.respond({'error': 'Öppna BAB från programmets startfil.'}, 403)
            return False
        last_activity = time.monotonic()
        return True

    def body(self):
        size = int(self.headers.get('Content-Length', '0'))
        if not 0 < size <= 6_000_000:
            raise ValueError('Filen är för stor eller tom.')
        value = json.loads(self.rfile.read(size))
        if not isinstance(value, dict):
            raise ValueError('Ogiltigt innehåll.')
        return value

    def do_GET(self):
        path = urlsplit(self.path).path
        try:
            if path.startswith('/api/') or path.startswith('/audio/'):
                if not self.authorized():
                    return
            if path == '/api/bootstrap':
                with database() as db:
                    books = [dict(r) for r in db.execute('SELECT id,title,position,voice,updated FROM books ORDER BY updated DESC')]
                    row = db.execute('SELECT value FROM settings WHERE id=1').fetchone()
                self.respond(dict(voices=VOICES, books=books, settings=json.loads(row['value']) if row else {}, capabilities=capabilities()))
            elif path.startswith('/api/book/'):
                with database() as db:
                    row = db.execute('SELECT * FROM books WHERE id=?', (path.rsplit('/', 1)[-1],)).fetchone()
                self.respond(dict(row) if row else {'error': 'Boken hittades inte.'}, 200 if row else 404)
            elif path == '/api/ping':
                self.respond({'ok': True})
            elif re.fullmatch(r'/audio/[a-f0-9]{64}\.(?:wav|mp3)', path):
                self.send_file(CACHE / path.rsplit('/', 1)[-1], 'audio/wav' if path.endswith('.wav') else 'audio/mpeg')
            elif path in ['/', '/index.html', '/app.js', '/core.js', '/style.css', '/logo.svg', '/favicon.ico']:
                name = 'index.html' if path == '/' else path[1:]
                mime = {'.html':'text/html; charset=utf-8', '.js':'text/javascript; charset=utf-8', '.css':'text/css; charset=utf-8', '.svg':'image/svg+xml', '.ico':'image/x-icon'}
                self.send_file(ROOT / 'web' / name, mime[Path(name).suffix])
            else:
                self.respond({'error': 'Sidan finns inte.'}, 404)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception:
            logging.exception('Read failed')
            self.respond({'error': 'Kunde inte läsa den sparade informationen.'}, 500)

    def send_file(self, file, mime):
        if not file.exists():
            self.respond({'error': 'Filen finns inte.'}, 404)
            return
        size = file.stat().st_size
        start, end = 0, size - 1
        requested = self.headers.get('Range', '')
        if requested and mime.startswith('audio/'):
            match = re.fullmatch(r'bytes=(\d+)-(\d*)', requested)
            if not match or int(match[1]) >= size:
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.end_headers()
                return
            start = int(match[1])
            end = min(int(match[2]) if match[2] else end, end)
            if end < start:
                self.send_error(416)
                return
        self.send_response(206 if requested and mime.startswith('audio/') else 200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(end-start+1))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if mime.startswith('audio/'):
            self.send_header('Accept-Ranges', 'bytes')
            if requested:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        else:
            self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self'; media-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        self.end_headers()
        with file.open('rb') as f:
            f.seek(start)
            remaining = end-start+1
            while remaining:
                block = f.read(min(65536, remaining))
                if not block:
                    break
                self.wfile.write(block)
                remaining -= len(block)

    def do_POST(self):
        if not self.authorized():
            return
        path = urlsplit(self.path).path
        try:
            value = self.body()
            if path == '/api/speak':
                self.respond(get_speech(value.get('text'), value.get('voice')))
            elif path == '/api/book':
                title, text = value.get('title'), value.get('text')
                if not isinstance(title, str) or not title.strip() or len(title)>160:
                    raise ValueError('Ange en titel med högst 160 tecken.')
                if not isinstance(text, str) or not text.strip() or len(text)>MAX_TEXT:
                    raise ValueError('Boken måste innehålla text, högst 1 000 000 tecken.')
                if not any(c.isalnum() for c in text):
                    raise ValueError('Texten behöver innehålla ord eller siffror.')
                book_id = value.get('id') or str(uuid.uuid4())
                if not re.fullmatch(r'[a-f0-9-]{36}', book_id):
                    raise ValueError('Ogiltigt bok-ID.')
                voice = value.get('voice', 'female-01')
                if voice not in VOICE_MAP:
                    raise ValueError('Ogiltig röst.')
                text = text.replace('\r\n', '\n').replace('\r', '\n')
                if any(len(w)>3000 for w in re.findall(r'\S+', text)):
                    raise ValueError('Texten innehåller ett för långt ord. Lägg in mellanslag eller radbrytningar.')
                position = max(0, min(int(value.get('position', 0)), len(text.split())))
                with database() as db:
                    db.execute('INSERT INTO books VALUES (?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET title=excluded.title,text=excluded.text,position=excluded.position,voice=excluded.voice,updated=excluded.updated',
                               (book_id, title.strip(), text, position, voice, time.time()))
                self.respond({'id': book_id})
            elif path == '/api/position':
                with database() as db:
                    row = db.execute('SELECT text FROM books WHERE id=?', (value.get('id'),)).fetchone()
                    if not row:
                        raise ValueError('Boken hittades inte.')
                    position = max(0, min(int(value.get('position', 0)), len(row['text'].split())))
                    voice = value.get('voice', 'female-01')
                    if voice not in VOICE_MAP:
                        raise ValueError('Ogiltig röst.')
                    db.execute('UPDATE books SET position=?,voice=?,updated=? WHERE id=?', (position, voice, time.time(), value['id']))
                self.respond({'ok': True})
            elif path == '/api/delete':
                with database() as db:
                    db.execute('DELETE FROM books WHERE id=?', (value.get('id'),))
                self.respond({'ok': True})
            elif path == '/api/settings':
                settings = {k: value[k] for k in ['fontSize','fontFamily','volume','theme','speed','follow','lastBook','voiceMode'] if k in value}
                with database() as db:
                    db.execute('INSERT INTO settings VALUES(1,?) ON CONFLICT(id) DO UPDATE SET value=excluded.value', (json.dumps(settings),))
                self.respond({'ok': True})
            elif path == '/api/shortcut':
                if os.name != 'nt':
                    raise ValueError('Skrivbordsgenvägen kan skapas i Windows.')
                from windows_shortcut import create_shortcut
                try:
                    create_shortcut(ROOT)
                except Exception as exc:
                    logging.exception('Native shortcut failed')
                    raise ValueError('Genvägen kunde inte sparas på skrivbordet. ' + str(exc)) from exc
                self.respond({'ok': True})
            elif path == '/api/quit':
                self.respond({'ok': True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                self.respond({'error': 'Åtgärden finns inte.'}, 404)
        except (ValueError, TypeError, OverflowError) as exc:
            self.respond({'error': str(exc)}, 400)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass
        except Exception:
            logging.exception('Request failed')
            self.respond({'error': 'Ljudet kunde inte skapas eller informationen kunde inte sparas. Kontrollera att hela BAB-programmet är installerat. Din bok finns kvar.'}, 503)

def launch(url):
    for base in [os.environ.get('PROGRAMFILES(X86)', ''), os.environ.get('PROGRAMFILES', '')]:
        edge = Path(base) / 'Microsoft/Edge/Application/msedge.exe'
        if edge.is_file():
            subprocess.Popen([str(edge), f'--app={url}', '--new-window', '--window-size=1420,940'],
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            return
    webbrowser.open(url)

def main():
    initialize()
    logging.basicConfig(filename=DATA / 'bab.log', level=logging.WARNING, encoding='utf-8')
    def warm_local_voices():
        try:
            from offline_speech import warmup
            warmup()
        except Exception:
            logging.exception('Local voices could not be loaded')
    threading.Thread(target=warm_local_voices, daemon=True).start()
    port = int(os.environ.get('BAB_PORT', '0'))
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    server.daemon_threads = True
    url = f'http://127.0.0.1:{server.server_port}/#token={TOKEN}'
    if sys.stdout:
        print(url, flush=True)
    if '--no-browser' not in sys.argv and os.environ.get('BAB_NO_BROWSER') != '1':
        launch(url)
    def idle_shutdown():
        while True:
            time.sleep(30)
            if time.monotonic() - last_activity > 180:
                server.shutdown()
                break
    threading.Thread(target=idle_shutdown, daemon=True).start()
    try:
        server.serve_forever()
    finally:
        server.server_close()

if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        if sys.stdout:
            raise
        if os.name == 'nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(0, f'BAB kunde inte starta.\n\n{exc}', 'Better Audio Books', 16)
        else:
            raise
