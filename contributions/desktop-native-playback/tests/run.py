"""Co-install independent contributions in an owned temporary module directory."""
import argparse
from pathlib import Path
import shutil,sys,tempfile,unittest
p=argparse.ArgumentParser();p.add_argument('--prefetch-package',type=Path,required=True);a=p.parse_args()
root=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as directory:
    for source in (root/'src',a.prefetch_package.resolve()/'src'):
        for file in source.glob('*.py'):shutil.copyfile(file,Path(directory)/file.name)
    sys.path.insert(0,directory)
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.discover(str(root/'tests'),pattern='test_*.py'))
    raise SystemExit(not result.wasSuccessful())
