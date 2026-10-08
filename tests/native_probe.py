"""Run only with the installed app's bundled Python, on a disposable Mac."""
from pathlib import Path
import importlib
import json
import os
import platform
import socket
import sys
import tempfile
import time
import traceback

resources = Path(sys.argv[1])
mode = sys.argv[2]
packages = resources / ('mac-' + platform.machine()) / 'packages'
sys.path[:0] = [str(resources / 'app'), str(packages)]
os.environ['BAB_MAC_PACKAGES'] = str(packages)
for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[variable] = '1'


def imports():
    for name in ('AppKit', 'Foundation', 'WebKit', 'objc', 'webview', 'numpy', 'onnxruntime', 'piper'):
        importlib.import_module(name)
        print('IMPORT OK:', name, flush=True)


def offline():
    import server
    import offline_speech as speech
    def blocked(*args, **kwargs):
        raise AssertionError('Offline voice attempted a network connection')
    socket.socket.connect = blocked
    with tempfile.TemporaryDirectory() as cache:
        for gender in ('female', 'male'):
            text = 'Här testar vi en helt ny svensk berättelse utan internet.'
            started = time.monotonic()
            audio, timings = speech.synthesize(text, server.VOICE_MAP[gender + '-01'], cache)
            assert audio.startswith(b'RIFF') and len(timings) == len(text.split())
            assert list(speech._voices) == [gender]
            options = speech.load_voice(gender).session.get_session_options()
            assert options.intra_op_num_threads == 1
            assert options.get_session_config_entry('session.intra_op.allow_spinning') == '0'
            print(json.dumps({'voice': gender, 'seconds': time.monotonic() - started,
                              'wav_bytes': len(audio), 'word_timings': len(timings)}), flush=True)


def cocoa():
    # Invoke the shipped host with its real Cocoa engine. Instrument only the
    # test controller to inspect readiness and close the otherwise interactive app.
    import webview
    import mac_launcher
    original_create, original_start = webview.create_window, webview.start
    windows, result = [], {}
    def create(*args, **kwargs):
        window = original_create(*args, **kwargs)
        windows.append(window)
        return window
    def inspect_window():
        try:
            deadline = time.monotonic() + 25
            while time.monotonic() < deadline:
                if windows[0].run_js("typeof ready !== 'undefined' && ready === true && document.getElementById('reader') !== null"):
                    break
                time.sleep(.25)
            else:
                raise AssertionError('Cocoa window did not load and initialize BAB within 25 seconds')
            assert 'offline_speech' not in sys.modules, 'Startup unexpectedly imported offline models'
            cpu, wall = time.process_time(), time.monotonic()
            time.sleep(3)
            result.update(ready=True, idle_cpu_seconds=time.process_time() - cpu,
                          idle_wall_seconds=time.monotonic() - wall)
            print(json.dumps(result), flush=True)
        except Exception:
            result['error'] = traceback.format_exc()
            print(result['error'], flush=True)
        finally:
            if windows:
                if result.get('ready'):
                    windows[0].run_js('setVolume(.37); void 0;')
                windows[0].destroy()
    def start(**kwargs):
        return original_start(func=inspect_window, **kwargs)
    webview.create_window, webview.start = create, start
    mac_launcher.main()
    assert result.get('ready') and not result.get('error'), result
    import server
    with server.database() as db:
        settings = json.loads(db.execute('SELECT value FROM settings WHERE id=1').fetchone()['value'])
    assert settings['volume'] == .37, 'Closing the native window did not save settings'
    print('CLOSE SETTINGS OK', flush=True)


assert sys.platform == 'darwin', 'Native Mac tests must run on macOS'
{'imports': imports, 'offline': offline, 'cocoa': cocoa}[mode]()