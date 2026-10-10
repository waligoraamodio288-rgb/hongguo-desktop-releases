# HEVC 原生与渐进播放接入代码

HEVC 先实际尝试硬解，失败后只重试一次软解；软解失败或持续跟不上再回退 H.264。网络慢进入缓冲，源不可读提示重试，不把下载失败判断为解码失败。无需等整集下载或转码：libmpv 读取鉴权 Range 输入，H.264 回退也在首批完整 HLS 片段就绪后播放。音频由原生内核解码和变速，使用 Windows 默认设备、WASAPI 共享输出。

这是发行仓库的接入材料，**合并本 PR 不会改变已发布应用**。需要维护者移入私有源码并发布；不附完整应用、EXE、原 bundle、签名/账号协议、真实视频或凭证。与 #187 配合下载后3集；暂停整集预加载由独立补丁提供，基线仍是约12秒预读。

## 模块与接线

`desktop_stream.py` 负责有界 Range、取消、源校验和 CENC 按包解密输入；`desktop_native.py` 负责 Windows 子窗口、默认音频、倍速、硬软解与输入转发；`desktop_hls_service.py` 负责鉴权会话和释放；`desktop_codec.py` 描述真实编解码轨道并提供可用时的 HLS 包复制。`desktop_hls.py`/`desktop_hls_budget.py` 是回退编码参考实现，已有编码器可按契约适配；其中 AUTO 解码与 #188 相同，不需要重复打补丁。

宿主只在后台解析媒体，返回已完成本地 Path 或 `ProgressiveSource(url, request=authorized_request, identity=stable_id, key=authorized_content_key)`。本包不实现上游 API 或密钥获取。复用完整原片前必须确认写入已完成；不能把后台正在写的非空文件当缓存，也不要等待旧下载锁才能启动新选的一集。Range 内存16MiB、原生包内存32MiB；第三方临时磁盘缓存由后续暂停补丁开启。

用 `NativeHost(parent_pid=owned_desktop_pid, dll_path=verified_dll)` 创建原生宿主，交给 `HlsJobs(..., native=native)`；`make_router` 必须使用宿主会话鉴权并仅监听本机回环。source接口、控制、status、DELETE都属于该job。所有成功、失败、切集、超时和退出路径必须释放原生音频/窗口、Range源及会话目录。不得接收客户端指定进程、HWND、文件、设备、mpv命令或解密密钥。

需共同接入 #187 的两个模块。渐进当前源使用 `source_loader`；后三集使用完整文件 `download_loader`，并传 `source_status=desktop_stream.source_progress`。source加载、描述轨道及native模式选择都发生在编码槽之前；原生播放不占编码槽。只有copy/h264编码前取得槽，finally始终调用finish，取消旧会话先于启动新会话。

前端提供 `desktopNativePlayback` 和 `desktopCodecHls` 两个入口。宿主需提供 `w0(url)`（返回受信回环origin、会话url和key）、`desktopLegacyHls` 与 `ek`（分别为既有普通/窗口HLS控制器，支持注入codecFetch），以及已有media、callbacks和preparation契约。将原React播放入口接到 `desktopNativePlayback`，不直接拼接/覆盖发行EXE。依然保留原按钮、快捷键、全屏、小窗、选集及连播；native故障回退保留位置、暂停、倍速和音量。不要把浏览器HEVC探测结果当机器原生硬解结论。

`frontend-native.js` 持续轮询同一会话，暴露真实buffer范围；配合 #189 更新原灰条，暂停不停止轮询。更新或关闭后忽略旧请求回执。HE-AACv2限制的是HLS包复制资格，不影响已识别HEVC进入原生音视频解码。

## 验证

Windows x64、Python3.11、Node18+。安装 `requirements-test.txt`；将 #187 的贡献目录作为明确依赖提供，测试会在临时目录拼装模块，不改安装包。

```pwsh
pwsh -NoProfile -Command "python -I contributions/desktop-native-playback/tests/run.py --prefetch-package <prefetch-contribution-dir>"
pwsh -NoProfile -Command "node contributions/desktop-native-playback/tests/test_frontend.cjs"
```

当前公开测试共31项：本轮30项通过、1项可选本地HEVC输入测试跳过。Node覆盖轨道协商、位置/暂停/倍速恢复、只回退一次、旧回执与源失败不误转码。新增真实合成Opus输入转AAC-LC、seek共同时间原点、取消和预算回归；已有AAC继续直拷。新增两个确定性取消竞争测试，防止DELETE后prepare注册残留会话。公开fixture是合成媒体及公开测试密钥，不含提供方视频。硬解失败由受控驱动测试，未人为破坏真实GPU。

先前实际Tauri/WebView2已验证本机硬解dxva2-copy、强制软解、2x/3x、默认音频、首帧早于整片下载、缓冲恢复、暂停seek、切集、EOF连播及一次H.264回退。真实CENC输入的解码帧与已有明文一致。以上是本机接线结果；公开模块测试不能代替维护者私有源码与真实窗口验收。A-V数字来自内核时钟，没有物理声画、跨设备CPU/温度/功耗结论。

`src/libmpv-source.json` 记录测试用DLL的第三方来源；DLL不随本PR分发。当前适配固定SHA256 `34780746a0273a4fcae42dfe262a28984a426a238939474afd3a1561b450bbef`。维护者应核验来源及匹配API，按实际mpv/FFmpeg构建履行第三方许可与对应源码义务；升级后重新验收，不能仅改摘要绕过核验。[mpv手册](https://mpv.io/manual/stable/)说明解码与缓存选项。

[Issue对应关系与关闭条件](ISSUES.md)。回滚时在私有源码revert播放接线和新增模块，恢复原HLS入口；保留用户原片与观看记录，不直接删除未知缓存。材料提交、应用接入、发布与Issue验收分别记录。

复审修复：max_jobs限制总会话数；max_workers只限制copy/H.264实际编码，native准备不占编码槽。HlsJobs在有会话时自行启动回收线程，无后续请求也按idle_seconds清理，宿主shutdown调用jobs.close()。Range连接超时3秒、无数据读超时10秒，Timeout/ConnectionError最多尝试3次；每次重新校验Range/validator并丢弃失败的部分块，取消在读取和退避间检查。协议错误不重试；重试耗尽才报告source-read。[Requests超时说明](https://requests.readthedocs.io/en/stable/user/advanced/#timeouts)。新增真实3.2秒HTTP停顿恢复、重试关闭响应、取消、编码并发和无请求到期回归。

第二轮复审：截断 Range 丢弃后有界重试；弱 ETag 仅比较身份，不发送 If-Range；未出首帧的 EOF 先重试软件解码，再明确失败；EOF 后 seek 清除 ended，恢复播放保留所选目标。当前 Python 33 项通过、1 项可选 HEVC 跳过，Node 回归通过。

修复最新原生回执：描述与fallback共用AAC-LC资格判定，其余AAC profile转AAC-LC；无首帧EOF软件重试从原请求位置开始；close如线程仍存活返回pending，host/job/output保留，DELETE202，前端有界等待204才启动HLS，取消会话由reaper继续清理。新增真实AAC重编码及生命周期回归。 当前Python38项通过、1项可选HEVC跳过；Node回归通过。
