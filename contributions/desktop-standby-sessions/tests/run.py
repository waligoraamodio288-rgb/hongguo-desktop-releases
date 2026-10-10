"""Assemble exact public dependencies and apply only this PR's deltas."""
import argparse,hashlib,json,shutil,subprocess,sys,tempfile,unittest
from pathlib import Path

p=argparse.ArgumentParser()
p.add_argument('--native-package',type=Path,required=True)
p.add_argument('--prefetch-package',type=Path,required=True)
a=p.parse_args();package=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as temp:
    root=Path(temp);backend=root/'backend';backend.mkdir()
    for source in (a.native_package/'src',a.prefetch_package/'src'):
        for file in source.glob('*.py'):
            (backend/file.name).write_text(file.read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
    shutil.copytree(a.native_package/'tests',root/'native-tests',ignore=shutil.ignore_patterns('__pycache__'))
    for file in (root/'native-tests').glob('*.py'):
        file.write_text(file.read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
    baseline=json.loads((package/'BASELINES.json').read_text(encoding='utf-8'))
    for entry in baseline['files']:
        target=root/entry['path']
        assert hashlib.sha256(target.read_bytes()).hexdigest()==entry['baseSha256'],entry['path']
        patch=package/'src'/(target.stem+'.patch')
        subprocess.run(['git','-c','core.autocrlf=false','-C',str(root),'apply','--check',str(patch)],check=True)
        subprocess.run(['git','-c','core.autocrlf=false','-C',str(root),'apply',str(patch)],check=True)
        assert hashlib.sha256(target.read_bytes()).hexdigest()==entry['patchedSha256']
    sys.path[:0]=[str(backend),str(a.prefetch_package.resolve()/'tests')]
    suite=unittest.TestSuite()
    # Each original suite retains its own fixtures; new ownership tests run
    # against the same patched dependency modules as all prior regressions.
    for tests in (root/'native-tests',a.prefetch_package/'tests',package/'tests'):
        loader=unittest.TestLoader()
        suite.addTests(loader.discover(str(tests.resolve()),pattern='test_*.py'))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(not result.wasSuccessful())
