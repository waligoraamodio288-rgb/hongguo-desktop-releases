import {createComments} from '../../desktop-comments-frontend/src/comments.mjs';
import {createDanmaku} from '../../desktop-danmaku-frontend/src/danmaku.mjs';
import {createEmojis} from '../../desktop-social-emojis/src/emojis.mjs';
import {installSocialStyles,createSelection} from './layout.mjs';

// Resolve endpoints with the host's existing trusted loopback/authentication owner.
export function createSocialUI({React,jsxRuntime,resolveEndpoint}) {
  let social;
  const emojis=createEmojis({jsxRuntime,read:(...args)=>social.read(...args)});
  const danmaku=createDanmaku({React,jsxRuntime,emojis,
    read:(...args)=>social.read(...args),preference:(...args)=>social.preference(...args),set:(...args)=>social.set(...args)});
  social=createComments({React,jsxRuntime,resolveEndpoint,emojis,danmaku,installStyles:installSocialStyles});
  return {...social,Selection:createSelection({React,jsxRuntime,set:social.set}),emojis,danmaku};
}
