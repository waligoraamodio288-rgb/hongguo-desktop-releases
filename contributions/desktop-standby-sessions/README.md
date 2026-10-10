# 下一集备用会话接入补丁

当前集结束后才创建下一集播放器，会把下载、轨道探测和首帧解码都留到切集时。本补丁允许提前准备一个下一集会话；未缓存时仍正常读取 Range，完整原片可直接复用。备用原生窗口保持隐藏、暂停和静音，旧会话保留到前端确认新画面接管。

这是发行仓库的源码接入材料，合并 PR 不会改变已发布应用。依赖 #187 的 `9d037eb49bd70e11998235d9287ca5f58d0534d5` 和 #204 的 `b330417cd2ab9ddc1a558cd897ffb423b7f407fc`。不依赖暂停整集预加载 #205；不附完整应用源码、EXE、DLL、视频或用户数据。

## 接入

先接入上述贡献模块。`BASELINES.json` 给出 LF 规范化后的输入、输出 SHA256；`src/*.patch` 是针对公开模块的增量，不能对发行 EXE 使用。测试入口会在临时目录核对摘要、检查并应用补丁，保留此前并发、取消、超时、配额和音轨回退修复。`test_desktop_native.patch` 仅补齐原测试的 Win32 可见性模拟。

生产应用三个 backend 补丁，并在原 `HlsJobs` 接线中加入 `on_activate=prefetch.promote`。既有 `on_start=prefetch.begin`、`before_work=prefetch.before_work`、`on_finish=prefetch.finish`、`source_loader=prefetch.load_source` 保持一致。宿主 CORS 的允许请求头加入 `x-desktop-prewarm-parent`，沿用现有来源白名单、会话鉴权和回环监听，禁止使用通配来源。

POST `/desktop/hls?...` 时传 `x-desktop-codec-negotiation: 1` 和 `x-desktop-prewarm-parent: <当前job UUID>`。服务器验证同剧、紧邻下一集、零偏移、父会话有效和最多一个备用。旧客户端不传新头时行为不变。能力接口增加 `standbyPlayback: 1`。

HLS 在首帧可播放后 POST `/{id}/activate`；原生在 `outputReady` 后发送包含位置和 `visible:true` 的 control；收到输出、可见状态和 revision ACK 后，再 POST `/{id}/activate` 完成提升。control 返回仅代表排队成功，此时仍保留父关系。原生先等待旧音频暂停 ACK，才允许新会话解除静音/暂停。前端还须等待新窗口可见、输出就绪和 control revision 生效，才能 DELETE 旧会话。配套前端 PR 提供这部分交接。

备用不推进当前预缓存代际。提升复用已经准备的 source，后台刷新后续下载队列，不再次解析或下载当前源；HLS 实际编码未结束时继续持有原编码槽。释放父会话会级联取消未提升的子会话；提升后子会话独立存活。仍使用 #204 的总会话上限、编码信号量、到期回收和 shutdown close。

## 验证与边界

```pwsh
pwsh -NoProfile -Command "python -I contributions/desktop-standby-sessions/tests/run.py --native-package <native-contribution-dir> --prefetch-package <prefetch-contribution-dir>"
```

入口同时运行原生贡献、预缓存贡献与本 PR 的生命周期回归；缺少 `DESKTOP_HEVC_TEST_SOURCE` 时，可选真实 HEVC 包一致性用例跳过。其他媒体由测试合成，包含 Opus 回退、Range/CENC、下载早于完整输入、取消和磁盘缓存配额。

本机融合候选此前通过43项真实 Tauri 状态检查，涵盖冷缓存、原生1x/2x/3x、HLS、预缓存接线及资源释放。这个候选和本公开补丁的依赖版本不同，公开组合另跑上述回归；不能把旧候选证据当作公开组合的视觉验收。当前没有连续画面录制证据，正式版仍有用户反馈黑屏，维护者需接入后按冷缓存、慢网、倍速、跳集和关闭场景实测。

回滚时撤销三个生产补丁及 `on_activate` 接线，恢复普通播放入口；保留原片缓存与用户观看记录。[Issue 关闭条件](ISSUES.md)。

本轮公开组合101项：100项通过、1项可选HEVC跳过。额外覆盖激活清除parent至异步提升之间的worker完成竞争，旧集元数据不被下一集覆盖。

后端回执修复：激活前保留父子取消关系；服务端核对真实可见/输出/revision后才提升。子控制提交失败恢复旧会话原先暂停状态；取消发生在异步提升前时，worker身份检查保护父集下载队列。
