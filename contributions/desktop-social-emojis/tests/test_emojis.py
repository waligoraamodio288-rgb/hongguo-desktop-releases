import copy
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from desktop_emoji_assets import validate_assets,catalog
FIXTURE={'[测试]':{'src':'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAFgQIAK32fWQAAAABJRU5ErkJggg==','resolution':1,'drawing':[{'color':[255,0,0],'alpha':1,'paths':[[[0,0],[1,0],[1,1],[0,1]]]}]}}
class EmojiTests(unittest.TestCase):
    def test_catalog(self): self.assertEqual(catalog(validate_assets(FIXTURE))['[测试]'],FIXTURE['[测试]']['src'])
    def test_bad_url(self):
        row=copy.deepcopy(FIXTURE); row['[测试]']['src']='https://example.invalid/tracker'
        with self.assertRaises(ValueError): validate_assets(row)
    def test_ass_coordinate_injection(self):
        for value in ('0}\\pos(0,0)',True,float('nan'),-1,2):
            row=copy.deepcopy(FIXTURE); row['[测试]']['drawing'][0]['paths'][0][0][0]=value
            with self.assertRaises(ValueError): validate_assets(row)
    def test_unknown_label(self):
        with self.assertRaises(ValueError): validate_assets({'not-a-tag':FIXTURE['[测试]']})
if __name__=='__main__': unittest.main()
