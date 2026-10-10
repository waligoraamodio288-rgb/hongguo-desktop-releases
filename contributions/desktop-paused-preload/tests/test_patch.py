"""Apply the exact patch to the native contribution, without application binaries."""
import argparse,hashlib,subprocess,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--native-package',type=Path,required=True);a=p.parse_args()
patch=Path(__file__).resolve().parents[1]/'enable-paused-preload.patch'
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory);(root/'backend').mkdir()
    target=root/'backend/desktop_native.py';target.write_bytes((a.native_package/'src/desktop_native.py').read_bytes())
    subprocess.run(['git','-C',str(root),'apply','--check',str(patch)],check=True)
    subprocess.run(['git','-C',str(root),'apply',str(patch)],check=True)
    assert hashlib.sha256(target.read_bytes()).hexdigest()=='541feefa79d388474fb77a9d82c41ded8b46e1d9744f4ca6cee219179b331c48'
    compile(target.read_text(encoding='utf-8'),str(target),'exec')
print('PASS: exact patch applies and matches installed tested implementation')
