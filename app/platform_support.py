"""Small platform boundary shared by both desktop editions."""
import os
from pathlib import Path
import sys

VERSION = '1.6.2'


def data_directory(platform=None, environ=None, home=None):
    platform = sys.platform if platform is None else platform
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    if environ.get('BAB_DATA_DIR'):
        return Path(environ['BAB_DATA_DIR'])
    if platform == 'win32':
        return Path(environ.get('LOCALAPPDATA', str(home / 'AppData' / 'Local'))) / 'Better Audio Books'
    if platform == 'darwin':
        return home / 'Library' / 'Application Support' / 'Better Audio Books'
    return Path(environ.get('XDG_DATA_HOME', str(home / '.local' / 'share'))) / 'Better Audio Books'


def capabilities():
    return {'version': VERSION, 'platform': sys.platform, 'desktopShortcut': sys.platform == 'win32',
            'backgroundVoices': sys.platform != 'darwin'}
