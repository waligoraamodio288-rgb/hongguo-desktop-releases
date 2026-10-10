import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from fastapi import FastAPI, Header, HTTPException
from fastapi.testclient import TestClient
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from desktop_social import SocialService, make_router

SID, VID, CID = '1000000000000000001', '2000000000000000001', '3000000000000000001'
class Provider:
    CFG = {'base_query': {'aid': '999'}}
    def __init__(self): self.calls = []; self.result = {'code':0,'data':{}}
    def get_episodes(self, sid): return {}, [{'index':1,'vid':VID,'duration':42.5}]
    def _episodes_body(self, sid): return {'series_id':sid}
    def _parse_episode_detail(self, sid, video):
        return {'followed_cnt':'18'}, [{'index':1,'vid':VID,'digged_count':'4','comment_count':'3'}]
    def api(self, method, path, **kwargs):
        self.calls.append((method,path,kwargs)); return self.result

def authorize(x_api_key: str = Header('')):
    if x_api_key != 'fixture-only': raise HTTPException(401, 'Unauthorized')

class SocialTests(unittest.TestCase):
    def setUp(self):
        self.provider=Provider(); self.service=SocialService(self.provider)
        self.app=FastAPI(); self.app.include_router(make_router(self.provider,authorize=authorize))
        self.client=TestClient(self.app); self.headers={'x-api-key':'fixture-only'}
    def test_required_auth_on_every_route(self):
        for route in self.app.routes:
            if route.path.startswith('/desktop/social'):
                self.assertEqual(self.client.get(route.path).status_code,401)
        self.assertEqual(self.provider.calls,[])
    def test_id_validation_and_read_only(self):
        base='/desktop/social/comments'
        for params in ({'series_id':'bad','ep':1},{'series_id':SID,'ep':0},{'series_id':SID,'ep':1,'cursor':'x'*8193}):
            self.assertEqual(self.client.get(base,params=params,headers=self.headers).status_code,422)
        self.assertEqual(self.client.post(base,headers=self.headers).status_code,405)
        self.assertEqual(self.provider.calls,[])
    def test_comment_variants_and_opaque_cursor(self):
        for kind,ctype,source,channel,group in [('episode',4,4,18,VID),('series',2,1,46,SID),('danmaku',20,601,1000,VID)]:
            self.service.comments(SID,1,kind,'opaque:+/==',30000)
            method,path,kwargs=self.provider.calls[-1]; body=kwargs['body']
            self.assertEqual(method,'POST'); self.assertIn('/list/'+group+'/v1/',path)
            self.assertEqual((body['comment_type'],body['comment_source'],body['server_channel']),(ctype,source,channel))
            self.assertEqual(body['cursor'],'opaque:+/=='); self.assertEqual(kwargs['max_retries'],1)
            if kind=='danmaku':
                self.assertEqual(body['business_param']['start_offset_time'],30000)
                self.assertEqual(body['business_param']['playlet_item_duration'],42500)
    def test_normalization_and_string_ids(self):
        self.provider.result={'code':0,'data':{'data_list':[{'comment':{'comment_id':CID,'common':{'content':{'text':'hi[笑哭]👍'},'user_info':{'base_info':{'user_name':'fixture'}}},'stat':{'digg_count':7},'expand':{'offset_time':1200}}}], 'common_list_info':{'cursor':'opaque','has_more':True,'total':9}}}
        page=self.service.comments(SID,1,'episode')
        self.assertEqual(page['items'][0]['id'],CID); self.assertEqual(page['items'][0]['text'],'hi[笑哭]👍')
        self.assertEqual(page['items'][0]['offset_ms'],1200); self.assertTrue(page['has_more'])
    def test_replies_common_uppercase(self):
        self.provider.result={'code':0,'data':{'reply_list':[{'reply_id':'4000000000000000001','Common':{'content':{'text':'reply'}},'stat':{}}], 'comment_list_info':{'cursor':'','has_more':True}}}
        page=self.service.replies(SID,1,CID)
        self.assertEqual(page['items'][0]['text'],'reply'); self.assertFalse(page['has_more'])
        body=self.provider.calls[-1][2]['body']; self.assertEqual(body['comment_source'],504)
        self.assertFalse(body['business_param']['need_count'])
    def test_stats_cache_refresh_and_scope(self):
        self.provider.result={'code':0,'data':{SID:{'video_data':{'fixture':True}}}}
        self.assertEqual(self.service.metrics(SID,1)['favorites'],18)
        self.service.metrics(SID,1); self.assertEqual(len(self.provider.calls),1)
        self.service.metrics(SID,1,True); self.assertEqual(len(self.provider.calls),2)
        self.service.stats_cache[SID]=(0,*self.service.stats_cache[SID][1:])
        self.service.metrics(SID,1); self.assertEqual(len(self.provider.calls),3)
    def test_unknown_episode_and_business_error(self):
        with self.assertRaises(HTTPException) as ex: self.service.comments(SID,2,'episode')
        self.assertEqual(ex.exception.status_code,404)
        self.provider.result={'code':7,'data':{}}
        with self.assertRaises(HTTPException) as ex: self.service.comments(SID,1,'episode')
        self.assertEqual(ex.exception.status_code,502)
    def test_internal_errors_are_redacted(self):
        def broken(*a,**k): raise RuntimeError('secret fixture detail')
        self.provider.api=broken
        response=self.client.get('/desktop/social/comments',params={'series_id':SID,'ep':1},headers=self.headers)
        self.assertEqual(response.status_code,502); self.assertNotIn('secret',response.text)
    def test_optional_emoji_provider(self):
        self.assertEqual(self.client.get('/desktop/social/emojis',headers=self.headers).json(),{'items':{}})
if __name__=='__main__': unittest.main()
