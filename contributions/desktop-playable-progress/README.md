# 浅灰轨道显示实际可播缓存范围（集成材料）

浅灰轨道表示已经转换好、可直接读取播放的范围；整集完成显示100%。粉色和滑块继续表示当前播放位置。暂停期间独立刷新，恢复不清空；只有 seek 窗口时保留未准备好的前缀。

原显示读取 WebView `video.buffered`，它是有上限的内存缓冲，不能代表磁盘完整缓存。本目录提供新写的范围计算模块、前端接入 helper、CSS 参考及独立测试。**本仓库没有私有应用源码，合并本材料不会更新已发布安装包。** 不包含原 JS bundle、EXE、私有完整模块、原片或观看记录。

## 后端接入

将 `src/desktop_playable_range.py` 放到私有 backend。原 Job 提供 directory、duration、window_origin、start_seconds、source、failed、cancelled/done Event；source 在 loader 成功后保存，duration 来自完整原片时间轴。现有鉴权 status handler 的结果增加：

```python
from desktop_playable_range import playable_range

# callback 必须校验完整缓存和当前策略，不是判断原片是否下载。
result["playableRange"] = playable_range(job, full_cache_ready=prefetch.cache.contains)
```

有 source 的会话先查询已校验完整缓存，从0开始也一样；可用时返回 [0, duration]，返回前再次检查取消/失败。否则读取 HLS EXTINF 与实际存在的连续片段，播放列表必须以 #EXTM3U 开始，统计前必须有指向 init.mp4 的正确 EXT-X-MAP；done + ENDLIST + complete.marker 才确认尾部时长。非零 seek 窗口返回 [window_origin, end]。失败/取消/未准备好返回 [0,0]。宿主负责原子完成 marker、固定本地 playlist、owner/路径与会话生命周期校验。

集成完整缓存复用依赖另一个 `desktop-prefetch-cache` 贡献的接口或作者等价实现。没有完整缓存模块时可省略 callback，此时只报告当前会话的磁盘覆盖范围。接口仅新增两个数字，不暴露 source 路径、媒体 URL 或鉴权信息；保留现有 status 鉴权。

## 前端接入

`src/playable-range.cjs` 使用 CommonJS 便于独立测试；维护者可将导出改成实际前端的 ESM/TypeScript 导出，逻辑保持一致。

```javascript
const poller = createRangePoller({
  fetchStatus: (id, { signal }) => authenticatedLocalStatus(id, { signal }),
  onRange: range => setPlayableRange(range),
});
// 创建新会话后 start(id)，切集先失效旧请求；卸载/释放会话 stop()。
// 若宿主已有 status poll，将校验和 epoch guard 接入原 owner，勿再创建第二套轮询。
// 原轨道：style={rangeStyle(playableRange, duration)}，保留现有播放位置计算。
```

轮询 preparing 为1.5秒、complete 为10秒，并在暂停时继续。完成后仍轮询，以反映完整缓存被驱逐或失效。每次请求由前一次结束后调度，避免叠加；fetchStatus 应设置宿主现有请求超时并遵守 AbortSignal。切集 start 清为 [0,0]，旧请求即使忽略 abort 也受 epoch 拦截。播放/暂停不调用 start/stop，timeline 更新只合并时间轴字段，不重置缓存状态。网络临时失败保留最近有效范围并重试；服务器返回变小范围时必须接受，不能永远取 max。

参考 `src/playback-track.css` 接入原轨道的 `--buffered-start`、`--buffered`，用现有 `--played` 绘制粉色位置。没有新增进度条或其它提示。local-HLS 模式初始范围 [0,0]，不能退回 video.buffered 冒充磁盘范围；原直连播放模式可继续使用自己的 buffer 逻辑。

## 公开验证

Python 3.10+、Node18+，在仓库根目录运行：

```powershell
pwsh -NoProfile -Command "python -I contributions/desktop-playable-progress/tests/test_range.py"
pwsh -NoProfile -Command "node --test contributions/desktop-playable-progress/tests/test_frontend.cjs"
```

15项 Python fixture 验证原片不算可播、磁盘增长、缺片、完整标记、seek 缺口、完整缓存 callback、失败/取消和坏 playlist；新增从0开始命中完整缓存、init 映射以及校验期间取消/失败、HLS必需首行的回归。6项 Node 测试验证完整/窗口样式、暂停刷新、恢复保留、切集旧回调、卸载、失败重试与失效缩短。它们不代替私有 API/React/WebView 接线验收。

## 本机真实结果与上游门禁

已在本机 Tauri/WebView2 真实播放器验证：暂停时播放位置停在10.288631秒，浅灰轨道从85.08%增长到100%，而 video.buffered 仅到28.866666秒；恢复后时间走到11.033491秒，灰条保持100%。这是本机已接线版本的证据，公开 helper 是便于维护者移植的接口形式，不能宣称上游已集成。

作者接入后须验证实际 status 鉴权/字段、真实前端切集与非零 seek、暂停后台增长、完整缓存即时铺满、恢复不清空以及旧请求失效，再发布。Related to #23；目前没有单独准确对应浅灰轨道语义的公开 Issue。本材料不自动关闭 Issue，#14/#64/#162 控件显隐/全屏不在范围。

回滚：私有源码 revert status 字段及轨道接线/helper，恢复原展示；无需删除完整缓存或用户数据。

复审补充：补上目标时长、兼容版本、片段时长和结束位置校验；非有限或越界的跳转起点返回空范围。

HLS校验按[RFC 8216](https://www.rfc-editor.org/rfc/rfc8216.html#section-4.3.3.1)检查必需的 TARGETDURATION、fMP4 MAP所需的VERSION>=6，以及片段时长和标签顺序。测试片段仍为fake字节，不能代替真实媒体解码。
