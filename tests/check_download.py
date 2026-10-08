from pathlib import Path
import hashlib
import sys

EXPECTED = 'e2d0300503ca88ef034d01f78b20185dee483a6e82137577208a9fada2db0412'
path = Path(sys.argv[1])
digest = hashlib.sha256()
with path.open('rb') as stream:
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(chunk)
if digest.hexdigest() != EXPECTED:
    raise SystemExit('Installer checksum mismatch; refusing installation.')
print('PASS: exact BAB 1.6.1 installer SHA256 verified.')
