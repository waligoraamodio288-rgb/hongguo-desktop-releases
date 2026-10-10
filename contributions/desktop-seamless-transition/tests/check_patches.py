"""Verify public bridge deltas and run original frontend regressions."""
import argparse,hashlib,json,shutil,subprocess,tempfile
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--native-package',type=Path,required=True);a=p.parse_args()
package=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as temp:
    root=Path(temp);frontend=root/'frontend';frontend.mkdir()
    for entry in json.loads((package/'BASELINES.json').read_text(encoding='utf-8'))['files']:
        target=root/entry['path']
        target.write_text((a.native_package/'src'/target.name).read_text(encoding='utf-8'),encoding='utf-8',newline='\n')
        assert hashlib.sha256(target.read_bytes()).hexdigest()==entry['baseSha256']
        patch=package/'src'/(target.stem+'.patch')
        subprocess.run(['git','-c','core.autocrlf=false','-C',str(root),'apply','--check',str(patch)],check=True)
        subprocess.run(['git','-c','core.autocrlf=false','-C',str(root),'apply',str(patch)],check=True)
        assert hashlib.sha256(target.read_bytes()).hexdigest()==entry['patchedSha256']
        subprocess.run(['node','--check',str(target)],check=True)
    # The original test discovers ../src relative to its file.
    (root/'src').mkdir();(root/'tests').mkdir()
    for file in frontend.glob('*.js'):shutil.copyfile(file,root/'src'/file.name)
    for file in (a.native_package/'tests').glob('*.cjs'):shutil.copyfile(file,root/'tests'/file.name)
    subprocess.run(['node',str(root/'tests/test_frontend.cjs')],check=True)
    subprocess.run(['node',str(package/'tests/test_frontend.cjs')],check=True)
print('PASS: exact public bridge patches, syntax and frontend regressions')
