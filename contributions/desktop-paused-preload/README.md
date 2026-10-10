# 暂停后继续加载当前集（补丁）

原生渐进播放此前 `cache-secs=12`、`demuxer-readahead-secs=12`，暂停后够约12秒就停止读取；前端轮询仍在运行，灰条停止反映的是实际预读已停止。此补丁扩展原生播放器缓存策略，暂停只停播放时钟，继续读取并保留当前集的媒体包，已有灰条按真实可播范围推进。

依赖 HEVC 原生播放贡献的 `desktop_native.py` 基线，SHA256 `359ed5df703aa03cf4346297f2ec55292de6fdfa846290a6f70eb7489269b115`。补丁应用后SHA256为 `541feefa79d388474fb77a9d82c41ded8b46e1d9744f4ca6cee219179b331c48`，与本机完成实际窗口验收的实现一致。基线漂移时先手工审查适配，不强行覆盖。

复用mpv原生磁盘缓存，文件留在既有UUID会话目录，关闭/切集释放。单会话磁盘软限512MiB，允许一轮读取超调；到限后停止文件增长，使用约12秒有界内存预读，不因此转码。Range内存16MiB、包内存32MiB，packet元数据仍占内存。`demuxer-cache-wait=no` 保证首帧就绪即播放，不等待整集。`cacheFileBytes/cacheComplete/preloadLimited`只是会话缓存状态，不含上游地址或内容密钥。[mpv官方缓存说明](https://mpv.io/manual/stable/#options-cache-on-disk)。

## 应用与验证

维护者把原生贡献接入私有backend后，在源码仓库检查并应用 `enable-paused-preload.patch`。这是发行仓库的接入材料，合并不等于用户已更新；不附EXE、视频或第三方DLL。

```pwsh
pwsh -NoProfile -Command "git apply --check <contribution-dir>/enable-paused-preload.patch"
pwsh -NoProfile -Command "git apply <contribution-dir>/enable-paused-preload.patch"
pwsh -NoProfile -Command "python -I contributions/desktop-paused-preload/tests/test_patch.py --native-package <native-contribution-dir>"
```

`tests/verify_preload.py` 可在Windows x64，用原生和 #187 的贡献目录、经核验的libmpv及自有媒体复测。它在临时目录拼装模块并打补丁，启动自己离屏父窗口和本机鉴权API，不启动或控制用户播放器。使用公开测试密钥将自有输入重新封装为限速CENC，测试只放行原生input-hook夹具，不能代替实际鼠标/键盘验收。

```pwsh
pwsh -NoProfile -Command "python -I contributions/desktop-paused-preload/tests/verify_preload.py --native-package <native-dir> --prefetch-package <prefetch-dir> --mpv <verified-libmpv-2.dll> --source <owned-hevc.mp4> --sha <sha256> --run <owned-output-dir>"
```

加 `--software` 强制软解；加 `--cache-budget 1048576` 注入1MiB测试预算。工具生成的本机报告和重新封装视频不提交上游。测试依赖沿用原生贡献的requirements-test.txt。

本机补丁可应用性通过；三个导出包组合的真实原生/API复测9项通过：暂停0秒、加载由局部推进到165.628秒整集，零H.264，恢复2x/3x、后三集原片下载、暂停seek和关闭释放通过。此前同一实现的实际Tauri/WebView2硬解及强制软解各12项验收通过：位置固定约4秒，原WR灰条从18.46%增长至100%；1MiB预算降级也保持原解码器。A-V来自内核时钟，未重新测CPU或物理输出。

维护者发布前仍须验证真实前端轮询与 #189 灰条、快速切集/取消/退出、默认音频及三倍速，并在慢网、断网、达限时检查没有误转码。后三集缓存策略由 #187 负责，此补丁仅改变当前原生会话预读。

Related to #23、#181；接入、发布并验证暂停继续预取与恢复后再考虑关闭。#202/#199/#173只关联部分路径，#151/#69仍需CPU/功耗复测。回滚用git revert本补丁，恢复约12秒预读；不要删除用户原片。完整Issue矩阵见原生播放贡献的ISSUES.md。
