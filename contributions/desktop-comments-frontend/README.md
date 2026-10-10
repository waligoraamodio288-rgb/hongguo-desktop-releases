# 按需加载评论与回复

这是发行仓库的源码接入材料，合并不会改变已发布应用。维护者仍需移入应用源码、完成真实播放器验收并发布。这里只提交新写功能、最小接线和匿名测试，不包含完整应用或安装包。

## 依赖

组合接入 desktop-danmaku-frontend、desktop-social-emojis 和 desktop-social-layout；HTTP 契约来自 desktop-comments-backend。组件工厂仅依赖宿主 React 和 jsxRuntime，测试无须安装 React。

## 接入与行为

createComments 接收 React、jsxRuntime、resolveEndpoint、installStyles、danmaku、emojis。推荐用布局包 bootstrap.mjs 一次组装；只提取现有前端新写的社交 owner，不包含发行应用 bundle。

将 Controls 放到现有播放器控制栏，Drawer 放到原选集 aside，继续使用同一个 media ref。Drawer 内部按 session.streamUrl 的 key 重建状态，每集默认选集。记忆展开抽屉也不会自动请求评论/回复/统计；主动选本集评论或整剧剧评才加载。切回选集/关抽屉/换集 abort 并忽略旧回执，回复在展开时加载、收起时取消。

resolveEndpoint 必须由原应用可信回环检查与密钥 owner 实现，返回 {url,origin,key}。不能把用户提供的任意 URL 原样当 origin。read 使用 x-api-key、credentials=omit、redirect=error、cache=no-store；15秒超时并关联会话取消。保持原快捷键，不注册 keydown 或 Escape 处理器。

页签固定为“选集、本集评论、整剧剧评”。仅选集隐藏标题、关闭和所有统计；两个评论模式保留。评论/回复分页去重并检测游标不前进，失败可重试，空结果显示空态。只有本集评论提供回复；图片评论显示占位，不实现图片下载。点赞/收藏仅展示总数，不提供远程写入。

## 验证

Python 3.10+、Node 18+；命令以 pwsh 为入口，在包含对应 contributions 的检出根运行。Python API 测试先安装本包 requirements-test.txt。浏览器组合测试需要 Chrome；也可传 --channel msedge。其他模块没有 npm 运行时依赖，React/JSX runtime 由宿主提供。

```pwsh
node contributions/desktop-comments-frontend/tests/test_shared.mjs
```

公开测试为人工构造输入，不连接上游。新导出模块已经独立验证；跨包 Chrome 用例由布局包统一维护。此前本机安装还完成53项窗口功能与21项原生像素检查，快/中/慢档（8/14/24秒）实测为161.25/92.5/53.75物理像素/视频秒；这些属于当时本机接线证据，不是本公开包在所有设备或上游发布后的保证。

回滚时撤回本包接线及新增模块，保留原播放入口、用户偏好和原片，不修改其他播放/缓存贡献。原快捷键不新增、不拦截。Issue 关闭以应用发布并验证为前提，见 [ISSUES.md](ISSUES.md)。

## 首轮审查修复

手动强制刷新只消费一次，关闭/切回选集后的普通打开重新使用缓存；新增实际 DOM 回归验证。
