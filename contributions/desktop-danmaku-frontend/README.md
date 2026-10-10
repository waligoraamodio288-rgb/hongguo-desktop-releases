# 弹幕设置与浏览器连续运动

这是发行仓库的源码接入材料，合并不会改变已发布应用。维护者仍需移入应用源码、完成真实播放器验收并发布。这里只提交新写功能、最小接线和匿名测试，不包含完整应用或安装包。

## 依赖

注入 desktop-comments-frontend 的 read/preference/set 和 desktop-social-emojis；CSS 来自 desktop-social-layout；原生模式还需 desktop-danmaku-backend 补丁。

## 接入与行为

createDanmaku 接收 React、jsxRuntime、read/preference/set 和 emojis。Settings 放在原弹幕开关位置，点击开关、悬停显示设置，无单独齿轮、无发送入口。与评论开关分别保存本机状态，移开延迟250ms收起；不改快捷键。

defaults={opacity:80,lanes:3,fontSize:28,duration:14}。duration 是单条完整滚动时间，滑块向右映射为更短时间/更快。旧版本速度按1.8比例迁移一次，版本标记为2，保留其他偏好。恢复默认、行数、字号、透明度、当前播放附近列表均走同一 owner。

start(media,endpoint,status) 返回清理函数。DOM 回退使用 requestAnimationFrame 和亚像素 translate3d，按媒体时间计算位置；暂停时间不变，seek 取消过期 generation，分页保留已有轨道。原生模式隐藏 DOM 层，通过 desktopdanmaku 事件向原生轨道发送有界日程，不能再用轮询重绘 OSD。只保留附近600条原始数据与最多300条已排轨条目；轨道满时丢弃过密弹幕。

网络错误5秒后重试，退出 abort 请求、取消帧、移除监听和节点，并清空原生日程。宿主更新 native currentTime 时仍需遵守原播放时钟契约；不能用每次轮询替换原生字幕。

## 验证

Python 3.10+、Node 18+；命令以 pwsh 为入口，在包含对应 contributions 的检出根运行。Python API 测试先安装本包 requirements-test.txt。浏览器组合测试需要 Chrome；也可传 --channel msedge。其他模块没有 npm 运行时依赖，React/JSX runtime 由宿主提供。

```pwsh
node contributions/desktop-danmaku-frontend/tests/test_motion.cjs
```

公开测试为人工构造输入，不连接上游。新导出模块已经独立验证；跨包 Chrome 用例由布局包统一维护。此前本机安装还完成53项窗口功能与21项原生像素检查，快/中/慢档（8/14/24秒）实测为161.25/92.5/53.75物理像素/视频秒；这些属于当时本机接线证据，不是本公开包在所有设备或上游发布后的保证。

回滚时撤回本包接线及新增模块，保留原播放入口、用户偏好和原片，不修改其他播放/缓存贡献。原快捷键不新增、不拦截。Issue 关闭以应用发布并验证为前提，见 [ISSUES.md](ISSUES.md)。
