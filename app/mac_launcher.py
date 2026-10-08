"""Cocoa/WKWebView host. Uses the same API, library, UI and voices as Windows."""
import logging
import os
from pathlib import Path
import secrets
import sys
import threading
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, os.environ.get('BAB_MAC_PACKAGES', str(ROOT / 'mac_packages')))


def main():
    if sys.platform != 'darwin':
        raise RuntimeError('Den här startfilen är avsedd för Mac.')
    # These limits apply only to BAB's own process, before importing native math libraries.
    for variable in ('OMP_NUM_THREADS', 'OPENBLAS_NUM_THREADS', 'VECLIB_MAXIMUM_THREADS', 'MKL_NUM_THREADS'):
        os.environ[variable] = '1'
    import server
    import webview
    server.initialize()
    logging.basicConfig(filename=server.DATA / 'bab.log', level=logging.WARNING, encoding='utf-8')
    http = server.ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)
    http.daemon_threads = True
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()

    # Load the selected offline model only after Play/Preview, not while opening the app.
    closing = threading.Event()
    may_close = threading.Event()
    window = None

    def persist_and_close():
        try:
            # run_js uses WKWebView directly; evaluate_js wraps code in eval,
            # which BAB's Content Security Policy correctly forbids.
            window.run_js("(async()=>{window.__babCloseSaved=false;try{if(typeof savePosition==='function'){await savePosition();await api('/api/settings',settingsSnapshot());}}finally{window.__babCloseSaved=true;}})(); void 0;")
            deadline = time.monotonic() + 4
            while time.monotonic() < deadline:
                if window.run_js("window.__babCloseSaved === true"):
                    break
                time.sleep(.05)
        except Exception:
            logging.exception('Could not save before closing the window')
        finally:
            may_close.set()
            window.destroy()

    def request_close():
        if may_close.is_set():
            return True
        if not closing.is_set():
            closing.set()
            threading.Thread(target=persist_and_close, daemon=True).start()
        return False

    class Bridge:
        def quit(self, token):
            if not isinstance(token, str) or not secrets.compare_digest(token, server.TOKEN):
                raise ValueError('Ogiltig session.')
            request_close()
            return True

    url = f'http://127.0.0.1:{http.server_port}/#token={server.TOKEN}'
    try:
        window = webview.create_window('BAB — Better Audio Books', url, js_api=Bridge(), width=1280, height=850,
                                       min_size=(820, 600), background_color='#f2f3ee')
        window.events.closing += request_close
        webview.start(gui='cocoa', private_mode=True, icon=str(ROOT.parent / 'BAB.icns'))
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=3)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        from platform_support import data_directory
        data = data_directory()
        data.mkdir(parents=True, exist_ok=True)
        logging.basicConfig(filename=data / 'bab.log', level=logging.WARNING, encoding='utf-8')
        logging.exception('BAB could not start')
        try:
            from AppKit import NSAlert
            alert = NSAlert.alloc().init()
            alert.setMessageText_('BAB kunde inte starta')
            alert.setInformativeText_('Kontrollera att du använder rätt Mac-version och att hela BAB.app finns kvar. Mer information finns i Bibliotek/Application Support/Better Audio Books/bab.log.')
            alert.addButtonWithTitle_('OK')
            alert.runModal()
        except Exception:
            pass
        raise
