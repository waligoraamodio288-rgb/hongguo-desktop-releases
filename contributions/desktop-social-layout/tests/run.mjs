// Cross-package behavior tests; fixtures contain no provider or user data.
import {createServer} from 'node:http';
import {readFile} from 'node:fs/promises';
import {resolve,dirname,sep} from 'node:path';
import {fileURLToPath} from 'node:url';
import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
const here=dirname(fileURLToPath(import.meta.url));
const args=process.argv.slice(2), option=(name,fallback)=>args.includes(name)?args[args.indexOf(name)+1]:fallback;
const root=resolve(option('--contributions-root',resolve(here,'../..')));
const require=createRequire(resolve(option('--node-modules',resolve(here,'../node_modules')),'_probe.cjs'));
const {chromium}=require('playwright');
const react=await readFile(resolve(dirname(require.resolve('react')),'umd/react.production.min.js'));
const reactdom=await readFile(resolve(dirname(require.resolve('react-dom')),'umd/react-dom.production.min.js'));
const html=`<!doctype html><meta charset="utf-8"><style>
*{box-sizing:border-box}body{margin:0;background:#151619;color:#eee;font:14px sans-serif}
.desktop-player{height:600px;display:flex;flex-direction:column}.desktop-player header{position:relative;height:60px;flex-shrink:0;padding:8px}
.desktop-player-layout{display:grid;flex:1;min-height:0;grid-template-columns:minmax(0,1fr) 360px}
.player-stage{position:relative;min-width:0;min-height:0;background:black}video{width:100%;height:100%;display:block}
.player-chrome{position:absolute;bottom:0;left:0;right:0;height:84px}.player-toolbar{display:flex;gap:8px;align-items:center;height:40px;padding:8px}
aside{display:flex;flex-direction:column;min-height:0;overflow:auto}.episode-fixture{padding:14px}
.window-controls{position:fixed;right:8px;top:8px;display:flex;gap:6px;height:32px;z-index:10}
.window-controls button,.player-mini-toggle{width:36px;height:32px}.window-pin{position:absolute;right:138px}
.player-mini-toggle{position:absolute;top:8px;right:160px}.return-button{width:120px;height:36px}
</style><div id="root"></div><script src="/react.js"></script><script src="/reactdom.js"></script>
<script type="module">
import {createSocialUI} from '/desktop-social-layout/src/bootstrap.mjs';
const O=window.React,b={jsx:(type,props,key)=>O.createElement(type,{...props,key}),jsxs:(type,props,key)=>O.createElement(type,{...props,key})};
const social=createSocialUI({React:O,jsxRuntime:b,resolveEndpoint:url=>({url,origin:location.origin,key:'fixture-only'})});
const {Selection,danmaku}=social;
window.calls=[]; window.hold=false;window.failComments=false;window.aborted=0;
const realFetch=window.fetch;
window.fetch=(url,options)=>{
 const path=new URL(url).pathname, params=new URL(url).searchParams;
 if(!path.startsWith('/desktop/social/'))return realFetch(url,options);
 window.calls.push({path,params:Object.fromEntries(params),headers:options.headers});
 if(window.hold && /comments|metrics|replies/.test(path))return new Promise((_,reject)=>options.signal.addEventListener('abort',()=>{window.aborted++;reject(new DOMException('Aborted','AbortError'));},{once:true}));
 if(window.failComments && path.endsWith('/comments'))return Promise.resolve({ok:false});
 let value={items:{}};
 if(path.endsWith('/emojis'))value={items:{'[测试]':'data:image/png;base64,iVBORw0KGgo='}};
 if(path.endsWith('/metrics'))value={likes:4,comments:3,favorites:18};
 if(path.endsWith('/danmaku'))value={items:[{id:'3000000000000000001',text:'test[测试]👍',offset_ms:1000}],next_offset_ms:30000,has_more:false,cursor:''};
 if(path.endsWith('/comments')||path.endsWith('/replies'))value={items:[{id:params.get('cursor')?'3000000000000000002':'3000000000000000001',author:'fixture',text:params.get('kind')==='series'?'series fixture':'constructor <img onerror=alert(1)>[测试]👍[未知]',likes:2,replies:path.endsWith('/replies')?0:1,created_at:0,image_count:0}],cursor:params.get('cursor')?'':'opaque:+/==',has_more:!params.get('cursor'),total:2};
 return Promise.resolve({ok:true,json:async()=>value});
};
function App(){
 const media=O.useRef(null),[ep,setEp]=O.useState(1);window.changeEpisode=()=>setEp(n=>n+1);
 const session={streamUrl:location.origin+'/stream?series_id=1000000000000000001&ep='+ep};
 return b.jsxs('div',{className:'app-shell',children:[
 b.jsxs('div',{className:'window-controls dark compact',children:['置顶','最小化','最大化','关闭'].map((label,i)=>b.jsx('button',{className:i===0?'window-pin':'','aria-label':label,children:label},label))}),
 b.jsxs('div',{className:'desktop-player',children:[
 b.jsxs('header',{children:[b.jsx('button',{className:'return-button',children:'返回片单'}),b.jsx(Selection,{media}),b.jsx('button',{className:'player-mini-toggle','aria-label':'迷你窗口',children:'小窗'})]}),
 b.jsxs('main',{className:'desktop-player-layout',children:[b.jsxs('div',{className:'player-stage',children:[b.jsx('video',{ref:media}),b.jsx('div',{className:'player-chrome',children:b.jsx('div',{className:'player-toolbar',children:b.jsx(social.Controls,{media,sessionKey:session.streamUrl})})})]}),
 b.jsxs('aside',{children:[b.jsx('div',{className:'episode-fixture',children:'剧集信息 · 1 2 3'}),b.jsx(social.Drawer,{session,media})]})]})]})]});
}
ReactDOM.createRoot(document.getElementById('root')).render(b.jsx(App,{}));
window.socialApi=social;window.danmakuApi=danmaku;
</script>`;
const server=createServer(async(req,res)=>{
 try{
  const url=new URL(req.url,'http://localhost');
  if(url.pathname==='/'){res.setHeader('content-type','text/html; charset=utf-8');res.end(html);return;}
  if(url.pathname==='/react.js'||url.pathname==='/reactdom.js'){res.setHeader('content-type','application/javascript');res.end(url.pathname==='/react.js'?react:reactdom);return;}
  const file=resolve(root,'.'+decodeURIComponent(url.pathname));
  if(!file.startsWith(root+sep)||!file.endsWith('.mjs'))throw Error('Forbidden');
  res.setHeader('content-type','application/javascript');res.end(await readFile(file));
 }catch{res.writeHead(404);res.end();}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
let browser;
const errors=[];let count=0;
function check(value,message){assert.ok(value,message);console.log('PASS '+message);count++;}
try{
 browser=await chromium.launch({channel:option('--channel','chrome'),headless:true});
 const page=await browser.newPage({viewport:{width:1280,height:720}});
 page.on('pageerror',e=>errors.push(String(e)));
 await page.addInitScript(()=>localStorage.setItem('hongguo:social','on'));
 await page.goto('http://127.0.0.1:'+server.address().port);
 await page.getByRole('tab',{name:'选集',exact:true}).waitFor({timeout:5000}).catch(async e=>{console.error('PAGE ERRORS',errors,'BODY',await page.locator('body').innerText());throw e;});
 const socialCalls=()=>page.evaluate(()=>calls.filter(c=>/comments|metrics|replies/.test(c.path)));
 check((await socialCalls()).length===0,'remembered open drawer starts on episodes without comments/metrics/replies');
 check(await page.getByRole('tab').allTextContents().then(x=>x.join('|')==='选集|本集评论|整剧剧评'),'selection tab is first');
 check(await page.locator('.desktop-social-header,.desktop-social-toolbar').count()===0,'selection hides title, close and all statistics');
 const initial=await page.locator('.desktop-player').boundingBox();
 await page.getByRole('button',{name:'打开选集',exact:true}).click();
 const wide=await page.locator('video').boundingBox();
 await page.getByRole('button',{name:'打开选集',exact:true}).click();
 const narrow=await page.locator('video').boundingBox();
 check(narrow.width<wide.width,'drawer opening narrows video');
 check(JSON.stringify(await page.locator('.desktop-player').boundingBox())===JSON.stringify(initial),'player outer frame remains fixed');
 await page.evaluate(()=>document.querySelector('.desktop-player').classList.add('mini'));
 check(await page.locator('aside').isHidden(),'mini mode hides an already enabled drawer');
 check(Math.abs((await page.locator('video').boundingBox()).width-wide.width)<1,'mini mode restores a single full-width video column');
 await page.evaluate(()=>document.querySelector('.desktop-player').classList.remove('mini'));
 await page.getByRole('tab',{name:'本集评论',exact:true}).click();
 await page.getByText('整剧收藏 18',{exact:true}).waitFor();
 check((await socialCalls()).some(c=>c.path.endsWith('/comments')),'comments load on explicit request');
 check(await page.locator('.desktop-social-header').count()===1,'comment tab retains title and close button');
 await page.getByRole('button',{name:'刷新互动计数',exact:true}).click();
 await page.waitForFunction(()=>calls.some(c=>c.path.endsWith('/metrics')&&c.params.refresh==='true'));
 await page.getByRole('tab',{name:'选集',exact:true}).click();
 await page.getByRole('tab',{name:'本集评论',exact:true}).click();
 await page.getByText('整剧收藏 18',{exact:true}).waitFor();
 check(await page.evaluate(()=>calls.filter(c=>c.path.endsWith('/metrics')).at(-1).params.refresh==='false'),'manual metrics refresh is consumed before ordinary reopening');
 check(await page.locator('.desktop-social-item > p img').count()===1,'comments render known emojis');
 check((await page.locator('.desktop-social-item > p').textContent()).includes('constructor <img onerror=alert(1)>'),'untrusted content remains text');
 check(await page.locator('.desktop-social-item img[onerror]').count()===0,'no HTML injection');
 await page.getByRole('button',{name:'加载更多评论',exact:true}).click();
 await page.waitForFunction(()=>document.querySelectorAll('.desktop-social-list > article').length===2);
 check((await socialCalls()).some(c=>c.params.cursor==='opaque:+/=='),'opaque cursor passes unchanged');
 await page.getByRole('button',{name:'查看 1 条回复',exact:true}).first().click();
 await page.locator('.desktop-social-replies article').waitFor();
 check((await socialCalls()).some(c=>c.path.endsWith('/replies')),'replies fetched only when expanded');
 await page.getByRole('tab',{name:'整剧剧评',exact:true}).click();
 await page.getByText('series fixture',{exact:true}).waitFor();
 check(await page.getByRole('button',{name:'查看 1 条回复',exact:true}).count()===0,'series review does not expose episode reply controls');
 await page.evaluate(()=>changeEpisode());
 await page.getByRole('tab',{name:'选集',selected:true}).waitFor();
 const before=(await socialCalls()).length;
 await page.waitForTimeout(100);
 check((await socialCalls()).length===before,'new episode resets to selection and makes no social fetch');
 await page.evaluate(()=>{hold=true});
 await page.getByRole('tab',{name:'本集评论',exact:true}).click();
 await page.waitForFunction(()=>calls.filter(c=>/comments|metrics/.test(c.path)).length>0);
 await page.getByRole('tab',{name:'选集',exact:true}).click();
 await page.waitForFunction(()=>aborted>=2);
 check(await page.evaluate(()=>aborted>=2),'returning to selection cancels comments and metrics');
 await page.evaluate(()=>{hold=false;failComments=true});
 await page.getByRole('tab',{name:'本集评论',exact:true}).click();
 await page.getByText('评论加载失败，请重试',{exact:false}).waitFor();
 check(await page.getByRole('button',{name:'重试',exact:true}).count()===1,'failed comments expose retry');
 await page.evaluate(()=>{failComments=false});
 await page.getByRole('button',{name:'重试',exact:true}).click();
 await page.locator('.desktop-social-item').first().waitFor();
 await page.getByRole('button',{name:'关闭评论抽屉',exact:true}).click();
 await page.mouse.move(0,0);
 await page.getByRole('button',{name:'弹幕',exact:true}).focus();
 await page.getByRole('region',{name:'弹幕设置',exact:true}).waitFor();
 check(await page.locator('input[type=range]').count()===4,'focus on same danmaku toggle exposes all settings without a shortcut');
 await page.keyboard.press('Tab');
 check(await page.getByRole('region',{name:'弹幕设置',exact:true}).isVisible(),'tabbing into settings keeps panel open');
 await page.getByRole('slider',{name:'移动速度',exact:true}).focus();
 await page.keyboard.press('End');
 check(await page.evaluate(()=>danmakuApi.settings().duration===4),'speed slider to the right means faster');
 await page.getByRole('button',{name:'恢复默认弹幕设置',exact:true}).click();
 check(await page.evaluate(()=>danmakuApi.settings().duration===14),'restore default duration is 14 seconds');
 check(await page.locator('textarea,input:not([type=range])').count()===0,'no comment or danmaku send field');
 await page.mouse.move(0,0); await page.waitForTimeout(300);
 for(const width of [1280,640,1600]){
  await page.setViewportSize({width,height:720}); await page.waitForTimeout(100);
  const boxes=await page.locator('.return-button,.desktop-selection-open,.player-mini-toggle,.window-controls button').evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return {name:n.textContent,left:r.left,right:r.right,top:r.top,bottom:r.bottom};}));
  check(boxes.every((a,i)=>a.left>=0&&a.right<=width&&boxes.slice(i+1).every(b=>Math.min(a.right,b.right)<=Math.max(a.left,b.left)||Math.min(a.bottom,b.bottom)<=Math.max(a.top,b.top))),`all individual top controls avoid overlap at ${width}px`);
 }
 await page.locator('.player-mini-toggle').evaluate(node=>node.style.width='96px');
 await page.waitForTimeout(100);
 const miniBox=await page.locator('.player-mini-toggle').boundingBox(),selectionBox=await page.locator('.desktop-selection-open').boundingBox();
 check(selectionBox.x+selectionBox.width+8<=miniBox.x,'mini button width changes update selection offset without resizing the window');
 // Respect the host keyboard owner: the module does not prevent or stop events.
 await page.evaluate(()=>{window.keySeen=0;window.addEventListener('keydown',()=>keySeen++);});
 await page.keyboard.press('Escape');
 check(await page.evaluate(()=>keySeen===1),'original keyboard handler still receives Escape');
 check(errors.length===0,'no browser exceptions: '+errors.join(';'));
 console.log(`PASS ${count} composition checks`);
}finally{await browser?.close();await new Promise(r=>server.close(r));}
