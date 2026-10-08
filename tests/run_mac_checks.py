"""Test the installed, unchanged BAB package on an actual hosted Mac runner."""
from pathlib import Path
import json
import os
import platform
import signal
import subprocess
import sys
import tempfile
import time

APP = Path('/Applications/Better Audio Books.app')
RESOURCES = APP / 'Contents/Resources'
ARCH = platform.machine()
PYTHON = RESOURCES / ('mac-' + ARCH) / 'runtime/bin/python3.12'
PROBE = Path(__file__).with_name('native_probe.py').resolve()
results = []


def run_phase(mode, timeout):
    with tempfile.TemporaryDirectory(prefix='bab-' + mode + '-') as data:
        env = dict(os.environ, BAB_DATA_DIR=data)
        process = subprocess.Popen([str(PYTHON), '-I', str(PROBE), str(RESOURCES), mode],
                                   env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, start_new_session=True)
        try:
            output, _ = process.communicate(timeout=timeout)
            passed = process.returncode == 0
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            output, _ = process.communicate()
            output += '\nTIMEOUT: native Mac test did not finish.\n'
            passed = False
        print('\n=== ' + mode + ' ===\n' + output, flush=True)
        for log in Path(data).glob('*.log'):
            print(log.name + ':\n' + log.read_text(errors='replace')[-16000:], flush=True)
        results.append({'test': mode, 'passed': passed})


def finder():
    # Launch the actual shipped bundle through LaunchServices, without changing
    # quarantine, Gatekeeper, signatures or files inside the installed app.
    process = subprocess.Popen(['/usr/bin/open', '-n', '-W', str(APP)],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    pids, visible = [], False
    try:
        # CoreGraphics window enumeration is read-only and requires no UI clicks.
        observer = '''import sys,json
sys.path.insert(0,sys.argv[1])
import Quartz
print(json.dumps([dict(pid=int(w.get('kCGWindowOwnerPID',0)),bounds={str(k):float(v) for k,v in w.get('kCGWindowBounds',{}).items()},layer=int(w.get('kCGWindowLayer',-1))) for w in Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly,0)]))'''
        packages = str(RESOURCES / ('mac-' + ARCH) / 'packages')
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            output = subprocess.check_output(['/bin/ps', '-axo', 'pid=,args='], text=True)
            pids = [int(line.strip().split(None, 1)[0]) for line in output.splitlines()
                    if str(RESOURCES / 'app/mac_launcher.py') in line]
            if pids:
                raw = subprocess.check_output([str(PYTHON), '-I', '-c', observer, packages], text=True, timeout=15)
                windows = json.loads(raw)
                visible = any(w['pid'] in pids and w['layer'] == 0 and
                              w.get('bounds', {}).get('Width', 0) >= 800 and
                              w.get('bounds', {}).get('Height', 0) >= 500 for w in windows)
                if visible:
                    break
            if process.poll() is not None and not pids:
                break
            time.sleep(.5)
        results.append({'test': 'actual Finder bundle launch and visible window', 'passed': visible})
        print('FINDER WINDOW:', visible, flush=True)
    finally:
        for pid in pids:
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        if process.poll() is None:
            process.terminate()
        try:
            output, _ = process.communicate(timeout=5)
            print(output, flush=True)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
        for name in ('launcher.log', 'bab.log'):
            path = Path.home() / 'Library/Application Support/Better Audio Books' / name
            if path.exists():
                print(name + ':\n' + path.read_text(errors='replace')[-16000:], flush=True)


def main():
    assert sys.platform == 'darwin' and ARCH in ('arm64', 'x86_64')
    assert PYTHON.is_file()
    print('HOST:', platform.platform(), ARCH, flush=True)
    for mode, timeout in [('imports', 45), ('offline', 90), ('cocoa', 60)]:
        run_phase(mode, timeout)
    try:
        finder()
    except Exception as exc:
        print('Finder check error:', repr(exc), flush=True)
        results.append({'test': 'Finder check', 'passed': False})
    print(json.dumps(results, indent=2))
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        with open(os.environ['GITHUB_STEP_SUMMARY'], 'a') as summary:
            summary.write('## BAB native Mac tests — ' + ARCH + '\n\n')
            for row in results:
                summary.write('- ' + ('PASS' if row['passed'] else 'FAIL') + ': ' + row['test'] + '\n')
            summary.write('\nThese tests do not prove Gatekeeper approval, audible playback, or performance on an M3 Mac.\n')
    raise SystemExit(0 if all(row['passed'] for row in results) else 1)


if __name__ == '__main__':
    main()