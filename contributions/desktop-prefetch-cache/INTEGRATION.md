# 私有源码接入契约

此目录不是安装器。将 `src/` 两个模块移入维护者的 backend，并按本契约接入现有会话管理器。公开测试中的 desktop_hls.py 只有异常类型，绝不能移入生产。

## 必需宿主接口

- `desktop_hls.EncodingCancelled`；`encode_hls(source, directory, on_ready=lambda: None, *, cancelled=lambda: False, start_seconds=0, on_window=None, video_mode="h264")`。适配器必须转发 `job.video_mode`（copy/h264）给 `prefetch.encode`；copy 包括 seek 窗口也不能静默退回 h264。取消须轮询；成功输出 init.mp4、segNNNNNN.m4s、index.m3u8（ENDLIST）以及最后提交的 `complete.marker`（内容 `desktop-hls-v1\n`）。失败不能提交 marker。
- 指纹默认读取实际 `desktop_hls.py`、`desktop_hls_budget.py` 及同目录存在的 `desktop_codec.py`；修改解码/编码/预算策略会使旧可播缓存失效。仅测试使用 `profile_files` 注入自造文件。生产若文件布局不同，必须传入实际策略文件，不能使用 fixture。
- 当前原片 loader 接收媒体 ID，可返回稳定本地 Path 或 ProgressiveSource；`download_loader` 返回已完整下载并核验的 Path，专供后三集。接入渐进源时传入 `source_status=desktop_stream.source_progress`；默认回调只适用于完整本地 Path。它必须幂等、线程安全、请求有超时，不能让前台与后台写坏同一原片。后台仅一个下载线程，但可与前台请求重叠。
- 剧集 loader 返回 `(details, [{"index": 正整数, "vid": "8至24位数字"}, ...])`。调度器排序、去重并取后续最多3个媒体。
- Job：id、directory、cancelled/ready Event、failed、start_seconds、video_mode（native/copy/h264，缺省h264）。directory 是宿主唯一会话输出目录；编码时不得预先建好目录。

## 会话生命周期接线

```python
prefetch = EpisodePrefetcher(
    source_loader=load_local_source, episode_loader=load_episodes,
    cache_root=playable_cache_root, encoder=encode_hls, ahead=3,
    status_path=optional_local_status_path,
    download_loader=load_complete_original,
    source_status=source_progress,  # 渐进源模块的共享状态回调

)
# 现有 HlsJobs 使用：source_loader=prefetch.load_source，encoder=prefetch.encode
```

在创建 job 后、启动线程前调用 `prefetch.begin(job, series_id, episode)`。worker 的 try 内先 `prefetch.load_source(...)`，再做 duration/seek 和播放模式选择。原生播放直接启动 native，不占编码槽；只有 HLS 编码前才调用 `prefetch.before_work(job)`，然后 `prefetch.encode(...)`。源下载不得占住编码槽，过期请求返回后先重查 job.cancelled 和代际。worker 的 finally 必须在所有成功、异常、取消路径调用 `prefetch.finish(job, series_id, episode, source_or_none)`；失败/取消标志须先写入 job。

若 Thread.start 或 begin 抛异常：设置 job.failed=True，调用 finish（source=None），移除未启动 job 并重新抛出；不得留下 foreground 占位。finish 的可选账本错误不得覆盖宿主主错误。应用关闭调用 prefetch.close；原片 loader 中已开始的请求不强杀，依赖宿主超时退出。

不要在 video.pause 时 release 会话或 close prefetch。暂停只停播放时钟，下载和转换由后端持续执行。切集 begin 会更新代际、取消后台编码并丢弃旧等待队列；已开始原片请求完成后不能污染新队列。before_work 会拒绝过期的排队前台任务；宿主仍须取消已在运行的旧会话，并在 finally 调用 finish 释放占位。

## 顺序、容量和复用

当前源可打开即启动后3集的顺序下载，与当前转换重叠；仅 video_mode=h264/copy 时，当前集完整可播后才串行转换后续，避免抢当前 CPU。native 模式只保留后3集原片下载，零 HLS/H.264 编码；h264/copy 模式的 seek 仅产生窗口时，后台先补齐当前整集。前台优先，整个调度器仅一个转换槽。本地缓存键包含原片内容 SHA256、源文件属性和策略指纹，避免同名同大小同时间戳的不同片源串集；缓存产物也逐文件校验 SHA256。命中后复制到独立会话，不再编码，所有媒体文件复制完才写完成标记。渐进源以宿主 cache_identity（包括内容标识/校验器）参与身份；copy/h264分开缓存。读取时会重新计算原片指纹，宿主须返回稳定的本地文件。

默认完整可播缓存配额2GiB，LRU 只清理带本 owner 标记的条目；会话副本不会被缓存驱逐。原片和活动会话容量继续归宿主原有机制负责，本包不等于磁盘总占用2GiB。临时输出的实时硬限制归 encoder/budget；遗留 stage 计入配额并保留待审计，不能任意删除未知文件。

`prefetch-status.json` 是可选本地诊断，含媒体身份和集数，不能直接作为公开日志上传。对外接口沿用原鉴权，不新增远端媒体接口。

## 作者接入后的必验项

真实播放时验证当前及后3集均完成；暂停期间队列继续；缓存集回放禁止原片网络和 encoder 调用仍可播放；损坏缓存重建；切集、seek、取消及线程启动失败均释放占位；播放器正常关闭和回滚不损失原片。测试 fake 片段不是有效媒体，不能代替真实解码和 HTTP/鉴权验收。

## 回滚

在私有源码 Git 中回退生命周期接线与两个模块，恢复原 loader/encoder；只按宿主 owner 校验清理可播缓存，保留原片及未知目录。发行包按维护者原发布流程回滚。
