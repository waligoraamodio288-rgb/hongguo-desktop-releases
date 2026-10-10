# PyAV AUTO 多线程解码（最小集成补丁）

在打开输入视频流后、首次 decode/demux 之前设置 `original.thread_type = "AUTO"`，允许 FFmpeg 选择帧级和片内并行；底层是 FFmpeg 的 C 实现，应用此处通过 Python/PyAV 调用。

本仓库不含私有源码。`enable-auto.patch` 只提供一行新增及最少上下文；由维护者在私有源码适配，不是安装包补丁。合并本材料不会改变已发布应用。

```powershell
pwsh -NoProfile -Command "git apply --check <材料目录>/enable-auto.patch"
pwsh -NoProfile -Command "git apply <材料目录>/enable-auto.patch"
```

若源代码位置漂移，应在实际输入流初始化处加入该行，不能放到开始解码之后。保留原 libx264 superfast、CRF20、分辨率、AAC copy 和时间轴处理；不增加同时转码集数。本补丁可独立集成；若配合预缓存包，编码模块指纹变化会使旧可播缓存失效。

## 公开验证

Python 3.10+、git、PyAV（本机18.1.0，含 libx264）：

```powershell
pwsh -NoProfile -Command "python -I contributions/desktop-frame-threading/tests/test_patch.py"
```

两项测试分别验证最小补丁可应用，以及实际 PyAV 编码12个自造帧后用 AUTO 解码完整12帧。不访问网络或私有视频。该小样本只验证 API/解码可用，不能代表 HEVC 整集性能。

## 本机真实 A/B（独立于 fixture）

同一62.392秒媒体、同一 PyAV/FFmpeg 和编码参数，默认解码到 AUTO：完整转换31.563 →27.188秒（减少约13.9%）；首可播片段1.172 →0.828秒。视频1497帧、音频2689帧/包一致，首尾音画偏差均小于0.047秒。四集完整解码、缓存重播和中途 seek 验证通过。单机单轮观测不能承诺跨设备加速或降低 CPU。

维护者复验：用同一有权使用的本地 HEVC 原片，在默认与 AUTO 两个私有 checkout 的独立进程分别编码到空目录；记录开始到首次 on_ready、开始到成功返回的 monotonic 时间；轮换顺序多次测量，并比较完整 HLS 解码帧数、音画首尾时间及 seek。按实际发行 PyAV/FFmpeg 版本和硬件验收后发布。不得只测单帧或只统计下载速度。

Related to #151、#69，仅为性能背景；未证明 CPU/功耗下降，不建议据此关闭这两个 Issue。多线程可能增加瞬时 CPU 和解码排队延迟，收益取决于片源与机器。回滚为移除该行或在私有源码 revert，并失效对应策略的可播缓存。
