# 暂停后继续加载当前集

原生播放器暂停后约12秒就停止预读，灰条随之停止。本补丁在暂停时顺序读取当前集的原片 Range 块，恢复播放和 seek 复用已存块；没有缓存时继续正常网络读取。只影响当前原生会话，后三集预取仍由 #187 负责。

依赖 #204 的 `b330417cd2ab9ddc1a558cd897ffb423b7f407fc`，各文件 LF 规范化后的补丁前后 SHA256 见 `BASELINES.json`。这是公开接入材料，合并不代表发行版已经修复；不包含 EXE、第三方 DLL、真实视频或账号数据。

## 缓存与生命周期

新增 `src/desktop_range_cache.py`，将原片块保存在已有 UUID 会话目录。写入 owner 在锁内先检查预算再写文件，默认单会话512MiB，物理文件不允许超调。关闭 mpv 的 append-only 磁盘缓存，保留约12秒、32MiB 有界包内存和16MiB Range 内存；达到磁盘预算或磁盘写失败后，后台停止填充，前台继续正常读取，沿用原解码器。

`cacheFileBytes/cacheComplete/preloadLimited` 来自块缓存 owner。只有原片完整时才报告完整范围；不把下载字节比例当作可播进度。退出和切集取消后台并关闭文件，随后由会话 owner 清理目录。非完整原片包含的块不能单独作为离线完整缓存。

## 应用与验证

将新增模块加入私有 backend，然后检查、应用 `enable-paused-preload.patch`。补丁覆盖 `desktop_stream.py`、`desktop_hls_service.py` 和 `desktop_native.py`；基线漂移时先适配，不强制覆盖。

```pwsh
pwsh -NoProfile -Command "git apply --check <contribution-dir>/enable-paused-preload.patch"
pwsh -NoProfile -Command "git apply <contribution-dir>/enable-paused-preload.patch"
pwsh -NoProfile -Command "python -I contributions/desktop-paused-preload/tests/test_patch.py --native-package <native-dir> --prefetch-package <prefetch-dir>"
```

测试核对摘要、补丁可应用性与编译，运行原生回归及缓存/验证器测试。覆盖无节流并发写入不超预算、重复与取消写入、完整块复用、磁盘失败，以及依据输入大小和限速计算验证期限。可选真实 HEVC 包一致性用例未配置时明确跳过。

`tests/verify_preload.py` 在 Windows x64 使用经核验的 libmpv、自有 HEVC 媒体、本机鉴权 API 和离屏父窗口；不控制用户播放器。它将自有媒体封装成测试 CENC，测试只放行 input-hook 夹具，不能代替实际鼠标/键盘验收。

```pwsh
pwsh -NoProfile -Command "python -I contributions/desktop-paused-preload/tests/verify_preload.py --native-package <native-dir> --prefetch-package <prefetch-dir> --mpv <verified-libmpv-2.dll> --source <owned-hevc.mp4> --sha <sha256> --run <owned-output-dir>"
```

`--software` 强制软解；`--cache-budget 1048576 --range-delay 0` 验证无节流1MiB硬预算。默认 Range 延迟0.12秒，验证期限随输入块数增长，最多3600秒；可用 `--preload-timeout` 在1至3600秒内显式指定。达限后采样3秒，最大物理文件大小不得超过预算，末尾1秒必须稳定。报告及媒体不提交。

维护者接入发布前，仍需验证真实前端 #189 灰条、冷缓存、慢网、断网、快速切集、默认音频与倍速恢复。此补丁不提供连续画面录制结论，也不宣称正式版已无黑屏。Related to #23、#181：发布并完成暂停加载/恢复验收后再考虑关闭；#202/#199 仅部分覆盖，不自动关闭。

回滚撤销补丁和新增模块，恢复约12秒预读；保留用户原片与观看记录。

当前公开组合43项：42项通过、1项可选HEVC跳过。自有40秒合成HEVC+AAC实际mpv/API复测：无节流1MiB硬预算8项通过、正常输入9项通过，涵盖暂停加载、2x/3x恢复、seek和释放；未据此宣称真实UI或像素连续性验收。
