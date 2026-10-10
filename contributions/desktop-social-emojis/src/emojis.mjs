export function createEmojis({jsxRuntime:b,read}) {
let desktopEmojiCatalog = Object.create(null), desktopEmojiRequest = null;
function desktopLoadEmojis(endpoint) {
  if (desktopEmojiRequest) return desktopEmojiRequest;
  desktopEmojiRequest = read(endpoint,'emojis').then(value=>{
    desktopEmojiCatalog = Object.assign(Object.create(null),Object.fromEntries(Object.entries(value.items || {}).filter(([name,src])=>
      /^\[[^\[\]\r\n]{1,16}\]$/.test(name) && typeof src==='string' && src.startsWith('data:image/png;base64,') && src.length <= 1024*1024)));
    window.dispatchEvent(new Event('desktopemojis'));
  }).catch(()=>{desktopEmojiRequest=null;});
  return desktopEmojiRequest;
}
function desktopEmojiParts(text) {
  return String(text).split(/(\[[^\[\]\r\n]{1,16}\])/g).filter(Boolean);
}
function DesktopEmojiText({text}) {
  return desktopEmojiParts(text).map((part,index)=>desktopEmojiCatalog[part]
    ? b.jsx('img',{className:'desktop-emoji',src:desktopEmojiCatalog[part],alt:part,title:part,draggable:false},index):part);
}


return {load:desktopLoadEmojis,parts:desktopEmojiParts,Text:DesktopEmojiText,get catalog(){return desktopEmojiCatalog;}};
}
