# 视频时间驱动的原生弹幕渲染

这是发行仓库的源码接入材料，合并不会改变已发布应用。维护者仍需移入应用源码、完成真实播放器验收并发布。这里只提交新写功能、最小接线和匿名测试，不包含完整应用或安装包。

## 依赖

依赖现有 #204 原生播放器接入包；取数复用 desktop-comments-backend 的 /danmaku，不复制签名/账号实现。表情素材通过 DanmakuTrack(assets=...) 注入。

## 接入与行为

将 src 的两个模块加入后端 import 路径，依次应用 patches/native-danmaku.patch、patches/native-events.patch。补丁基于公开 #204 的 desktop_native.py/frontend-native.js；集成到私有源码时按同名契约接线，先检查上下文。

DanmakuTrack 只在日程/设置变化时创建有绝对视频时间的 ASS 轨道。普通 time-pos 轮询不清空或重建；libass 在视频呈现时钟上移动字幕，因此暂停冻结、seek 与倍速跟随原播放器。替换时先 add/select 新轨道，再 remove 本包拥有的旧轨道，不移除其他轨道。MPV_EVENT_FILE_LOADED(8) 后重新加载。

控制协议新增 danmaku（最多300条，每条 text≤200字符、offset_ms≤86400000、lane=0..5）和 danmakuSettings（精确四个整数：opacity10..100、lanes1..6、fontSize18..36、duration4..24）。保持原控制鉴权、会话/窗口归属，拒绝任意 mpv 命令、用户 URL、ASS 指令与文件路径。

普通文本中的反斜杠和花括号用全角显示，避免 ASS 注入。render 失败仅标记 danmakuFailed，不中断音视频。没有本地表情素材时保留标签原文；emoji package 可注入经 validate_assets 校验的 PNG/矢量，原生 Unicode 彩色与复杂 ZWJ 表现仍依赖字体和 libass，不能保证所有系统一致。

该包处理弹幕轨道，不包含暂停预缓存 #205 的改动。独立补丁不得覆盖 #204/#205 之后的其他修复。

## 验证

Python 3.10+、Node 18+；命令以 pwsh 为入口，在包含对应 contributions 的检出根运行。Python API 测试先安装本包 requirements-test.txt。浏览器组合测试需要 Chrome；也可传 --channel msedge。其他模块没有 npm 运行时依赖，React/JSX runtime 由宿主提供。

```pwsh
python -X utf8 -m unittest discover -s contributions/desktop-danmaku-backend/tests -v
```

公开测试为人工构造输入，不连接上游。新导出模块已经独立验证；跨包 Chrome 用例由布局包统一维护。此前本机安装还完成53项窗口功能与21项原生像素检查，快/中/慢档（8/14/24秒）实测为161.25/92.5/53.75物理像素/视频秒；这些属于当时本机接线证据，不是本公开包在所有设备或上游发布后的保证。

回滚时撤回本包接线及新增模块，保留原播放入口、用户偏好和原片，不修改其他播放/缓存贡献。原快捷键不新增、不拦截。Issue 关闭以应用发布并验证为前提，见 [ISSUES.md](ISSUES.md)。
