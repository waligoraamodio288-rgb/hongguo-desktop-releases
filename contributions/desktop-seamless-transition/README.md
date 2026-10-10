# 提前预热与首帧交接

在当前集还剩12秒实际播放时间时，提前创建下一集的隐藏播放器。倍速按实际剩余时间计算；当前集缓冲时优先恢复当前播放。切集复用已经准备的会话、下载数据和首帧，继承倍速与音量；下一集尚未准备好时继续正常加载，不能保证任意网速下无等待。

这是发行仓库的接入材料，合并后仍需维护者移入私有应用源码并发布。依赖后端 `contributions/desktop-standby-sessions`、#187，以及 #204 的 `b330417cd2ab9ddc1a558cd897ffb423b7f407fc`。后端不依赖 #205 的暂停整集磁盘缓存补丁。

## 接线

对 #204 公开 `frontend-native.js`、`frontend-codec.js` 应用本目录两个补丁，加入 `frontend-seamless.js`。它们沿用 `w0`、`desktopLegacyHls`、`ek` 和原有 callbacks 契约。`BASELINES.json` 记录 LF 规范化后的补丁前后摘要。不要直接覆盖发行 bundle。

在原 React 播放流程中保存 preparation 引用，并在 timeupdate/倍速改变后调用 `desktopShouldPrewarm(media)`。它使用完整时间轴与窗口原点，不能只看当前 HLS 小窗口 duration。条件满足、连播开启且确有紧邻下一集时，解析下一集播放 URL 后调用 `desktopPrepareNext(nextUrl, media)`，每个当前 media 只调用一次；解析完成后重查当前集身份，过期结果不得创建预热。

自动切到该集时，将 preparation 传给 `desktopNativePlayback(nextMedia, nextUrl, 0, callbacks, preparation)`。原控制器 dispose 会通过 `desktopRetainPicture` 保留原生会话或 HLS 最后一帧。不要在新控制器接管前另行删除原生会话；HLS 画面遮罩须挂在跨集保持的 `.player-stage` 容器，避免 React 同时删除旧容器。

手动跳到其他集、换剧、关闭连播或退出时调用 preparation.dispose，忽略旧解析回执；claim 已转移的对象由新控制器释放。正常切集前不要重建相同 preparation，也不要把控制器 dispose 当作暂停处理。

原生预热保持隐藏、暂停、静音；交接等待输出、可见状态和 revision ACK。HLS 先保留旧帧，activate 返回后播放新视频，再在新视频帧回调后释放旧画面与控制器。解析、准备失败和未接管的保留资源有清理路径与90秒期限。宿主现有 controls、快捷键、全屏及选集仍消费原 media 接口。

## 验证

```pwsh
pwsh -NoProfile -Command "python -I contributions/desktop-seamless-transition/tests/check_patches.py --native-package <native-contribution-dir>"
```

测试检查补丁摘要、语法、原 codec/native 回归，并验证冷缓存请求、倍速阈值、隐藏静音首帧、所有权转移、HLS 属性/事件、延迟 activate ACK 和失败释放。测试没有访问真实视频或账号。

本机融合候选此前通过43项真实 Tauri 状态检查；公开增量另跑可移植回归，尚无连续像素级录屏证据，不能宣称正式版已消除黑屏。维护者接入后还需验证实际画面交接、慢网、无缓存、倍速、跳集、窗口变化与失败回退。

回滚时撤销两个桥接补丁、模块和 React 接线，恢复原 preparation 流程；不清理用户原片和观看记录。[Issue 关闭条件](ISSUES.md)。

回执修复：预热请求及JSON读取最长15秒且不越过90秒总期限；原生可见ACK最多2秒，超时释放并报错。HLS激活或play失败完整撤销接管并转普通加载；主动取消抑制过期错误。新增故障回归包含挂起fetch/JSON、隐藏/无帧/旧revision及激活期间退出。

原生交接采用两阶段确认：control排队后等待可见/输出/revision，再POST activate；该请求成功后才释放旧会话。
