"""Recreate the BAB 1.6.2 native payload from hash-locked public inputs.

No credentials, paid services, or signing are involved. Only the current
runner's architecture is included; all app sources and models match 1.6.2.
"""
from pathlib import Path, PurePosixPath
import base64
import hashlib
import json
import platform
import plistlib
import shutil
import subprocess
import tarfile
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parent.parent
BUILD=ROOT/'build'
STAGE=ROOT/'stage'
APP=STAGE/'Better Audio Books.app'
CONTENTS=APP/'Contents'
RES=CONTENTS/'Resources'
ARCH=platform.machine()


def fetch(url,sha):
    downloads=STAGE/'downloads';downloads.mkdir(parents=True,exist_ok=True)
    path=downloads/sha
    if not path.exists():
        request=urllib.request.Request(url,headers={'User-Agent':'BAB-free-native-tests'})
        with urllib.request.urlopen(request,timeout=120) as response,path.open('wb') as dest:
            shutil.copyfileobj(response,dest)
    assert hashlib.sha256(path.read_bytes()).hexdigest()==sha, 'Download checksum mismatch: '+url
    return path


def safe(name):
    rel=PurePosixPath(name)
    assert not rel.is_absolute() and '..' not in rel.parts and '\\' not in name,name
    return rel


def varint(n):
    result=bytearray()
    while n>127:result.append((n&127)|128);n>>=7
    result.append(n);return bytes(result)


def readvar(data,i):
    n=shift=0
    while True:
        b=data[i];i+=1;n|=(b&127)<<shift
        if not b&128:return n,i
        shift+=7


def fields(data):
    i=0
    while i<len(data):
        start=i;tag,i=readvar(data,i);number,wire=tag>>3,tag&7
        if wire==2:
            size,i=readvar(data,i);value=data[i:i+size];i+=size
        elif wire==0:_,i=readvar(data,i);value=None
        elif wire in (1,5):i+=8 if wire==1 else 4;value=None
        else:raise ValueError('Unsupported protobuf wire type')
        yield number,data[start:i],value


def patch_model(original,patch):
    top=list(fields(original));graph=next(value for number,raw,value in top if number==7)
    # BAB's existing model patch appends this GraphProto field. Keep its exact
    # position (NST has value_info records after the original output).
    graph=graph+patch
    return b''.join(varint(7<<3|2)+varint(len(graph))+graph if number==7 else raw for number,raw,value in top)


def main():
    assert platform.system()=='Darwin' and ARCH in ('arm64','x86_64')
    assert not APP.exists(), 'Use a clean test checkout'
    RES.mkdir(parents=True)
    shutil.copytree(ROOT/'app',RES/'app')
    shutil.copyfile(BUILD/'BAB.icns',RES/'BAB.icns')
    mac=RES/('mac-'+ARCH);mac.mkdir()
    row=next(r for r in json.loads((BUILD/'runtimes.json').read_text()) if r['arch']==ARCH)
    with tarfile.open(fetch(row['url'],row['sha256'])) as tar:
        tar.extractall(STAGE/'runtime-unpack',filter='data')
    shutil.move(STAGE/'runtime-unpack/python',mac/'runtime')
    for p in (mac/'runtime').rglob('*'):
        if p.is_file() and p.suffix.lower() in ('.exe','.dll','.pyd'):p.unlink()
    packages=mac/'packages';packages.mkdir()
    lock=json.loads((BUILD/(ARCH+'-dependencies.json')).read_text())
    for dep in lock:
        path=fetch(dep['url'],dep['sha256'])
        if dep['archive'].endswith('.whl'):
            with zipfile.ZipFile(path) as z:
                for info in z.infolist():
                    rel=safe(info.filename)
                    if info.is_dir() or rel.suffix.lower() in ('.exe','.dll','.pyd') or '__pycache__' in rel.parts:continue
                    if len(rel.parts)>2 and rel.parts[0].endswith('.data') and rel.parts[1] in ('purelib','platlib'):
                        rel=PurePosixPath(*rel.parts[2:])
                    dest=packages.joinpath(*rel.parts);dest.parent.mkdir(parents=True,exist_ok=True)
                    dest.write_bytes(z.read(info));dest.chmod(0o755 if dest.suffix in ('.so','.dylib') else 0o644)
        else:
            assert dep['name']=='proxy-tools'
            with tarfile.open(path) as tar:
                for member in tar:
                    rel=safe(member.name)
                    if not member.isfile():continue
                    if 'proxy_tools' in rel.parts:
                        rel=PurePosixPath(*rel.parts[rel.parts.index('proxy_tools'):])
                    elif rel.name.lower().startswith(('license','copying')):rel=PurePosixPath('proxy_tools')/rel.name
                    else:continue
                    dest=packages.joinpath(*rel.parts);dest.parent.mkdir(parents=True,exist_ok=True)
                    dest.write_bytes(tar.extractfile(member).read())
        print('Verified dependency:',dep['name'],dep['version'],flush=True)
    (packages/'BAB-dependencies.json').write_text(json.dumps(lock,indent=2))
    for row in json.loads((BUILD/'models.json').read_text()):
        original=fetch(row['url'],row['original_sha256']).read_bytes()
        data=patch_model(original,base64.b64decode(row['alignment_output_field_base64']))
        assert hashlib.sha256(data).hexdigest()==row['patched_sha256'], 'Patched model differs from BAB 1.6.2'
        (RES/'app/models'/row['name']).write_bytes(data)
        print('Verified original and BAB model:',row['name'],flush=True)
    info={'CFBundleDevelopmentRegion':'sv','CFBundleDisplayName':'Better Audio Books',
          'CFBundleName':'BAB','CFBundleIdentifier':'se.betteraudiobooks.bab',
          'CFBundleVersion':'1.6.2','CFBundleShortVersionString':'1.6.2',
          'CFBundleExecutable':'Better Audio Books','CFBundlePackageType':'APPL','CFBundleIconFile':'BAB.icns',
          'LSMinimumSystemVersion':'13.0','NSHighResolutionCapable':True,
          'NSRequiresAquaSystemAppearance':False,'CFBundleSupportedPlatforms':['MacOSX']}
    (CONTENTS/'Info.plist').write_bytes(plistlib.dumps(info))
    (CONTENTS/'PkgInfo').write_bytes(b'APPL????')
    executable=CONTENTS/'MacOS/Better Audio Books';executable.parent.mkdir()
    executable.write_bytes((BUILD/'mac-app-launcher.sh').read_bytes().replace(b'\r\n',b'\n'));executable.chmod(0o755)
    subprocess.run(['pkgbuild','--component',str(APP),'--install-location','/Applications',
                    '--identifier','se.betteraudiobooks.bab.pkg','--version','1.6.2',str(STAGE/'BAB-native-test.pkg')],check=True)


if __name__=='__main__':main()
