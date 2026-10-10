# 固定播放器外框、抽屉与顶部选集避让

这是发行仓库的源码接入材料，合并不会改变已发布应用。维护者仍需移入应用源码、完成真实播放器验收并发布。这里只提交新写功能、最小接线和匿名测试，不包含完整应用或安装包。

## 依赖

依赖上述两个前端与表情包；bootstrap.mjs 提供组合入口。原生布局补丁基于 #204 加 desktop-danmaku-backend 的两个补丁，不能直接应用到未接入的私有源码。

## 接入与行为

bootstrap.mjs 导出 createSocialUI({React,jsxRuntime,resolveEndpoint})，返回 Drawer、Controls、Selection 及依赖对象。它引用 contributions 下其他三个前端包，需共同检出。只调用一次工厂，不要在每次 render 创建新组件类型。

```js
const {Drawer,Controls,Selection}=createSocialUI({React,jsxRuntime,resolveEndpoint:trustedEndpoint});
// 原 header: <Selection media={mediaRef}/>
// 原 .player-toolbar: <Controls media={mediaRef} sessionKey={session.streamUrl}/>
// 原 aside（保留选集正文）: <Drawer session={session} media={mediaRef}/>
```

宿主保留 .app-shell、.desktop-player、header、.desktop-player-layout、.player-stage、.player-toolbar、aside、.window-controls、.window-pin、.player-mini-toggle 类。外框尺寸由现有窗口 owner 固定，layout 使用剩余空间的 grid、min-height:0/min-width:0；不得按评论内容重算窗口大小。抽屉开时右列占空间，视频缩窄；关时恢复。CSS只装一次。

顶部逐个测量控件：把原绝对定位的置顶按钮纳入窗口按钮行，选集放在迷你窗口及窗口按钮左侧，留12px间隔。使用 ResizeObserver 响应尺寸变化，不用固定右偏移覆盖实际测量。没有隐藏任何原生窗口按钮，也没有改置顶/快捷键。

原生模式依次应用 patches/native-layout.patch、patches/native-layout-events.patch（前提为弹幕后端两个补丁）。rect/occlusion 改动立即 flush，忙碌时下一轮不延迟250ms；设置弹层在现有原生表面切出可见区域，关闭恢复。SetWindowRgn 成功后所有权交给 Windows，失败路径释放本包 GDI 对象。不复制 #204/#205 的整个播放器。

tests/run.mjs 是跨包唯一浏览器回归入口，覆盖评论前端和布局，不在两个 PR 重复维护测试。真实 Chrome headless 使用匿名 HTTP fixture；不能替代 Tauri 原生 Win32 接入验收。

## 验证

Python 3.10+、Node 18+；命令以 pwsh 为入口，在包含对应 contributions 的检出根运行。Python API 测试先安装本包 requirements-test.txt。浏览器组合测试需要 Chrome；也可传 --channel msedge。其他模块没有 npm 运行时依赖，React/JSX runtime 由宿主提供。

```pwsh
npm --prefix contributions/desktop-social-layout ci
node contributions/desktop-social-layout/tests/run.mjs --channel chrome
```

公开测试为人工构造输入，不连接上游。新导出模块已经独立验证；跨包 Chrome 用例由布局包统一维护。此前本机安装还完成53项窗口功能与21项原生像素检查，快/中/慢档（8/14/24秒）实测为161.25/92.5/53.75物理像素/视频秒；这些属于当时本机接线证据，不是本公开包在所有设备或上游发布后的保证。

回滚时撤回本包接线及新增模块，保留原播放入口、用户偏好和原片，不修改其他播放/缓存贡献。原快捷键不新增、不拦截。Issue 关闭以应用发布并验证为前提，见 [ISSUES.md](ISSUES.md)。
