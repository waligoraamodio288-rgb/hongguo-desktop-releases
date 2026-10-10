import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from desktop_emoji_assets import validate_assets
spec=importlib.util.spec_from_file_location('compile_assets',ROOT/'tools/compile_assets.py')
compiler=importlib.util.module_from_spec(spec);spec.loader.exec_module(compiler)

class CompileTests(unittest.TestCase):
    def test_authored_image_compiles_to_png_and_vectors(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'fixture.png'
            image=Image.new('RGBA',(4,4),(255,0,0,255));image.putpixel((0,0),(0,0,0,0));image.save(path)
            assets=validate_assets(compiler.compile_assets({'[测试]':path}))
            row=assets['[测试]']
            self.assertEqual(row['resolution'],48)
            self.assertTrue(row['drawing'])
            self.assertTrue(any(group['color']==[255,0,0] for group in row['drawing']))

if __name__=='__main__':unittest.main()
