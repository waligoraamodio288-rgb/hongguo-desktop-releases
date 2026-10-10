"""Validate production deltas and optionally run dependency regressions."""
import argparse,hashlib,json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--native-package',type=Path,required=True)
p.add_argument('--prefetch-package',type=Path);a=p.parse_args()
package=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as directory:
    root=Path(directory);backend=root/'backend';backend.mkdir()
    for file in (a.native_package/'src').glob('*.py'):
        (backend/file.name).write_text(file.read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
    for file in (package/'src').glob('*.py'):shutil.copyfile(file,backend/file.name)
    entries=json.loads((package/'BASELINES.json').read_text(encoding='utf-8'))['files']
    for entry in entries:assert hashlib.sha256((root/entry['path']).read_bytes()).hexdigest()==entry['baseSha256']
    patch=package/'enable-paused-preload.patch'
    for extra in (['--check'],[]):
        subprocess.run(['git','-c','core.autocrlf=false','-C',str(root),'apply',*extra,str(patch)],check=True)
    for entry in entries:
        target=root/entry['path'];assert hashlib.sha256(target.read_bytes()).hexdigest()==entry['patchedSha256']
        compile(target.read_text(encoding='utf-8'),str(target),'exec')
    sys.path.insert(0,str(backend))
    suite=unittest.TestSuite()
    for pattern in ('test_range_cache.py','test_verifier.py'):
        suite.addTests(unittest.TestLoader().discover(str(package/'tests'),pattern=pattern))
    if a.prefetch_package:
        for file in (a.prefetch_package/'src').glob('*.py'):shutil.copyfile(file,backend/file.name)
        suite.addTests(unittest.TestLoader().discover(str(a.native_package.resolve()/'tests'),pattern='test_*.py'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():raise SystemExit(1)
print('PASS: production patches, SHA and portable regressions')
