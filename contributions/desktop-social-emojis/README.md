# 评论与弹幕共享表情支持

这是发行仓库的源码接入材料，合并不会改变已发布应用。维护者仍需移入应用源码、完成真实播放器验收并发布。这里只提交新写功能、最小接线和匿名测试，不包含完整应用或安装包。

## 依赖

前端由宿主注入 read 和 jsxRuntime；后端资源由同一份 validated assets 注入 /emojis 与 DanmakuTrack。素材处理本身无网络、无 APK 依赖。

## 接入与行为

createEmojis({jsxRuntime,read}) 提供 load/parts/Text/catalog。评论、回复、DOM弹幕、列表共用它；只接受已知方括号标签与本地 data:image/png;base64，未知标记和 Unicode emoji 保留原文，纯文本不经 innerHTML。无原型字典防止 constructor 等普通文本误匹配。并发首次请求共用一个 promise，失败可重试。

desktop_emoji_assets.py 从宿主明确指定的本地 JSON 加载并校验名字、PNG header/base64、分辨率、颜色/alpha、有界坐标和路径总数，随后同一份资源同时注入两端：

```python
assets=load_assets(host_owned_asset_file)
app.include_router(make_router(provider,authorize=existing_auth,
                               emoji_catalog=lambda:catalog(assets)))
track=DanmakuTrack(assets=assets)
```

原生补丁里的 DanmakuTrack() 默认无素材，需在该构造点显式传入上述 assets；不要只配置 /emojis，否则浏览器有表情而原生仍显示标签。PNG 用于 WebView；同一素材的 drawing 用于 ASS 连续移动，形状与文字共享时间，不轮询替换图片。

tools/compile_assets.py 接收宿主自己的“[标签]→本地图片路径”映射，输出 PNG 与48px/16色的 ASS 轮廓 JSON，运行需 Pillow。公开包只含人工合成测试数据，不分发 APK 内原始53张表情；维护者接入已有素材表后才有对应表情图。没有素材时原文可读，不猜测公网 URL。

普通 Unicode 在浏览器使用系统 emoji 字体；原生 libass 可能单色，复杂 ZWJ 组合与缺字受系统字体影响。此次没有实现发送或上传表情。

## 验证

Python 3.10+、Node 18+；命令以 pwsh 为入口，在包含对应 contributions 的检出根运行。Python API 测试先安装本包 requirements-test.txt。浏览器组合测试需要 Chrome；也可传 --channel msedge。其他模块没有 npm 运行时依赖，React/JSX runtime 由宿主提供。

```pwsh
python -X utf8 -m unittest discover -s contributions/desktop-social-emojis/tests -v
node contributions/desktop-social-emojis/tests/test_emojis.mjs
```

公开测试为人工构造输入，不连接上游。新导出模块已经独立验证；跨包 Chrome 用例由布局包统一维护。此前本机安装还完成53项窗口功能与21项原生像素检查，快/中/慢档（8/14/24秒）实测为161.25/92.5/53.75物理像素/视频秒；这些属于当时本机接线证据，不是本公开包在所有设备或上游发布后的保证。

回滚时撤回本包接线及新增模块，保留原播放入口、用户偏好和原片，不修改其他播放/缓存贡献。原快捷键不新增、不拦截。Issue 关闭以应用发布并验证为前提，见 [ISSUES.md](ISSUES.md)。

## 首轮审查修复

PNG 编译先限制到256px，再执行资源 schema 与16MiB总输出校验，失败不写输出；JS 标签正则按 Unicode 码点计数。新增大图、错误映射与九个非BMP emoji 标签回归，7项 Python 和 Node 测试通过。
