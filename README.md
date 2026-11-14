# 红果短剧｜Windows、Mac 测试版与 Android TV

> **Windows 1.0.28 修复版已发布**：修复首次播放准备遇到 CDN 跳转失败的问题；空缓存搜索、播放和切集已实测。[查看更新与下载](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/tag/v1.0.28)。

在 Windows 电脑上找剧、接着上次看。支持搜索、收藏、本机观看进度、选集、倍速和自动连播。

**由渠道有数独立维护 · 免费使用 · Windows 正式版 1.0.28**

**[渠道有数网站](https://shiyuemenghui.top/?utm_source=github&utm_medium=readme&utm_campaign=custom_domain)** · [安装帮助](https://shiyuemenghui.top/help/install/?utm_source=github&utm_medium=readme&utm_campaign=custom_domain)

网站暂有部分网络无法访问；遇到打不开时，可直接使用下方 GitHub 安装包和本页说明。

**[下载 Windows 安装程序](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/download/v1.0.28/hongguo-1.0.28-windows-x86_64-setup.exe)**　｜　[三步安装](#三步开始使用)　｜　[下载与安装说明](#下载与安装说明)　｜　[全部版本](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases)

Windows 10 / 11 **x64（64 位）** · 安装包 **111.6 MiB**。普通使用只需下载 `.exe`，不需要下载源码 ZIP、`.sig` 或 `latest.json`。

## 按设备选择下载

| 你的设备 | 当前版本与入口 | 安装前确认 |
| --- | --- | --- |
| Windows 电脑 | [1.0.28 正式版 · 下载 Setup](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/download/v1.0.28/hongguo-1.0.28-windows-x86_64-setup.exe) | Windows 10/11 x64 |
| Android 电视、盒子、投影 | [0.5.9 测试版 · 选 ARM32 / ARM64](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/blob/main/TV.md) | Android 5.0+，按系统架构选包 |
| Mac | [1.0.9 beta.2 · 下载与安装说明](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/tag/mac-v1.0.9-beta.2) | M 系列、macOS 14+；测试版，暂不支持 Intel |

分享 Windows 下载请使用[固定最新版入口](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/latest)；TV 和 Mac 请分享上方各自入口。无需关注、回帖或私信取包。

## Windows 1.0.28：在电脑上找剧，关掉后接着看

- **直接在电脑上追剧**：搜索、选集、倍速、小窗与自动连播，无需安卓模拟器。
- **保留自己的追剧记录**：支持保存登录、本机观看进度和手机云片单入口。11 月 14 日隔离复制现有登录后，两次启动保持登录，缓存片单、本地历史与进度一致；原账号文件未改变。
- **遇到中断有恢复入口**：本版修复首次准备所需文件遇到 CDN 跳转失败，保留校验与已有手动恢复入口。
- **更新与通知**：软件内检查更新，公告横幅提供版本说明和使用提醒。

**[下载 Windows 1.0.28 安装包](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/download/v1.0.28/hongguo-1.0.28-windows-x86_64-setup.exe)** · **[查看更新与已知问题](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/tag/v1.0.28)** · [反馈问题](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/issues/new?template=bug-report.yml)

本次实测范围：1.0.28 从空数据、空 WebView 缓存开始，搜索“东北后妈”返回5条，第1→4→1集声画及时间推进；另测“馋坏全皇宫”和“闪婚遇上裴先生”，分别返回5、6条。提供现有 WebView2 的 Windows 沙盒完成1.0.27→1.0.28升级、数据保留和回退。结果只覆盖本轮环境及样本，不代表全部设备或剧目。

**已知反馈（2026-11-13）**：部分 1.0.27 用户仍报告搜索失败或无法播放，见 [#1410](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/issues/1410)、[#1411](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/issues/1411)、[#1412](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/issues/1412)。遇到问题请附系统、版本、剧名和集数；不要提交账号凭据。不要反复重装或删除资料来尝试解决。

[观看旧版 42 秒操作演示：老板键与 3 倍速](https://www.bilibili.com/video/BV1SbH16iECg/)（录制版本 1.0.10，仅用于了解基本操作；以当前界面为准）。Windows 与 Android TV 的本机进度各自保存，TV 暂不跨设备同步。

<!-- mac-beta-promotion-start -->
## Mac 公开测试版：邀请 M 系列用户体验

**Mac 1.0.9 beta.2 · Apple Silicon（M1 及更新芯片）· macOS 14+ · 免费测试**

Mac 上也可以搜索找剧、收藏和接着本机进度看，提供 Command 快捷键、全屏/迷你窗口与设置入口。欢迎自愿体验并反馈，帮助完善 Mac 操作。

**[下载 Mac 测试版 DMG](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/tag/mac-v1.0.9-beta.2)**　｜　**[反馈 Mac 问题](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/issues/new?template=macos.yml)**　｜　[参与测试与查看进度](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/issues/359)

下载 `Hongguo_1.0.9-beta.2_aarch64.dmg`，约158 MiB；其余 ZIP 是第三方源码/许可，普通用户无需下载。当前仅提供 M 系列版，Intel 请暂勿下载。应用为 ad-hoc 签名、尚未公证，首次打开可能被系统拦截；遇到提示请反馈，不要关闭系统保护。

beta.2 修复原生全屏和偏好关闭交互，同一候选在 M2 上通过2个原生用例、108项断言；启动仍可能较慢，真实声音、长时间播放及安装升级/回退仍待验证。Mac 测试版不替代 Windows 正式版，也不承诺所有剧集和网络均可用。**下方演示和安装步骤为 Windows 版，不能视作 Mac 实测。**
<!-- mac-beta-promotion-end -->

## 电视、盒子、投影与平板

**0.5.9 测试版 · ARM32 / ARM64 · Android5.0+**

**[下载32位 ARMv7 · 1.27 MB](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/download/tv-v0.5.9/HongguoTV-0.5.9-arm32.apk)** ｜ **[下载64位 ARM64 · 4.11 MB](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/download/tv-v0.5.9/HongguoTV-0.5.9-arm64.apk)**

0.5.9 更新主取源并正式接入真人剧、漫剧关键词搜索。两部反馈样本的第4、5、10集在小米Android13平板真实ARM32/ARM64进程持续播放超过30秒，跨过10秒失败位置；实际720p和1080p，第三集续播第四集通过。仅代表本轮样本与设备，不保证全部剧集或旧电视。

保持单播放器、单媒体工作线程、两槽缓存、单文件32MiB上限及64KiB分块下载；低内存自动最高480p，内存紧张时取消预取并释放封面。没有新增软件解码器或转码服务。若某集只有高清轨道，手动限制720p或低内存480p可能无法播放；性能充足且硬解支持的设备可尝试自动或1080p。

首次搜索需同意本机设备登记，AI搜索仅筛选热门片单。

[电视版安装与实测范围](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/blob/main/TV.md) · [反馈设备体验](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/issues/new?template=android-tv.yml)

## 软件界面

![红果桌面版 1.0.2 的发现页，含分类、排行榜、收藏和历史入口](assets/home-v1.0.2.png)

*1.0.2 正式安装包在隔离 Windows 环境中实拍的首页；图中剧目封面来自内容服务，具体内容和播放可用性以实际环境为准。*

第三方收录：[不死鸟 2026 年 9 月 23 日每日分享](https://iui.su/213/)。该条目现链接到本项目的发行列表，可在列表中查看当前正式版。

## 三步开始使用

收藏或分享[固定最新版入口](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/latest)，可减少旧文章停留在过期版本的问题。旧版用户可查看[升级与安装帮助](https://shiyuemenghui.top/help/install/#upgrade)；已是同版且正常使用，无需重复下载。

1. 通过上方链接下载 `hongguo-1.0.28-windows-x86_64-setup.exe`。

2. 升级前通过设置或托盘完全退出旧程序，再按安装程序完成安装；沿用原安装目录和用户资料，无需先卸载旧版本。已有可用 WebView2 时会复用，缺失时安装程序需联网补齐。如果进度条接近终点但仍显示执行 `guoban-webview2-setup.exe`，安装程序正在等待运行环境补装结束，请先不要关闭窗口或重复运行安装包。若在线补装失败、启动提示缺少 WebView2，或已知网络不稳定，可到[微软官方 WebView2 Runtime 下载页](https://developer.microsoft.com/en-us/microsoft-edge/webview2/)选择 **Evergreen Standalone Installer（x64）** 安装，再重试红果安装或启动。若安装进度长时间没有变化，请记录界面和发生时间后反馈。

3. 打开应用，浏览分类或搜索剧名，进入详情后播放。观看进度保存在桌面端，不代表同步手机红果 App 账号和历史。

如果详情页提示“桌面内容服务尚未就绪”，播放按钮此时不可点击。先等待约 1 分钟，再到“设置”→“播放服务”点“检查连接”；这个按钮只重新检测本机服务状态，不会重启服务。仍显示“未连接”时，从 Windows 通知区域右键红果托盘图标并退出，再重新打开应用，等待约 1 分钟后再检查一次。点窗口右上角的 × 不会完整退出程序。若仍未连接，请在[播放问题 #5](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/issues/5)补充 Windows 和应用版本、两次检查结果及提示原文；若曾对比不同网络，请注明是否同一台电脑。若已进入播放器却没有画面，再说明加载、黑屏或报错情况。没有 GitHub 账号可发邮件至[项目邮箱](mailto:WaligoraAmodio288@gmail.com)。无需提供账号、IP 或完整日志。目前原因尚未确认。

老板键默认 Ctrl+Shift+B，可在设置里调整。隐藏窗口时自动暂停播放，恢复后从原位置继续并保留倍速；原本手动暂停的视频仍保持暂停。

## 怎么找到其他季

播放时，在右侧选集区点“查找其他季”，滚动列表并核对完整标题、季数和版本，再点“选择此季”。不带季数后缀的同名条目可能是起始部分，仍需核对内容。等待切换时可点“收起其他季”取消；原视频暂停后可手动继续。

1.0.11 及以前没有此手动入口，可回到片单搜索完整主体剧名。例如“聚宝仙盆之杂灵根才是真BOSS”，不要漏掉“仙”字。候选来自标题匹配，可能不完整，也不保证每个条目始终可播放。

## 播放中断时

若播放器提示“播放中断，请重试当前集”，先点“重试”一次，再换另一部剧对照；随后到“设置”→“播放服务”点“检查连接”。[提交播放问题](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/issues/new?template=bug-report.yml)时请写明是否已安装并打开应用、点击播放后立即还是播了一段时间才中断、连接状态，以及重试和换剧的结果。无需提供账号、令牌或完整日志。这个提示可能对应多种失败，目前不能仅凭提示判断原因。

## 旧版无法播放，先检查哪个版本？

Windows 用户可先在设置里核对版本。当前正式版为 1.0.28；旧版用户请通过[固定最新版入口](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/latest)获取当前安装包。这个修复不代表所有网络、设备或剧集都能正常播放。更新后仍失败，请按上面的“播放中断时”步骤反馈版本、屏幕提示和换剧结果。

电视、盒子和平板请使用上方 Android TV 入口；真人剧、漫剧和 AI剧（AI 剧）分类独立，当前0.5.9提供ARM32与ARM64两种安装包。Windows 安装程序不能安装到电视。

## 版本变化与已知反馈

**当前 1.0.28：** 修复首次播放准备的 CDN 跳转处理，区分文件暂不可用和会话结果不明；保留原功能及用户资料。空缓存搜索、播放与切集、登录恢复、安装升级和回退已验证。部分用户反馈仍需逐例确认，不能据此认定所有搜索和播放故障已解决。[正式版说明](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/tag/v1.0.28)。

下方为旧版本记录，按当时状态保留，不代表当前功能缺失或当前登录行为。

**1.0.20（历史）：** 改进发现页、搜索结果与记录、播放器选集及续看、手机登录恢复与收藏操作，并增加本地反馈草稿和公开回复查看入口。详见[1.0.20 正式版说明](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/tag/v1.0.20)；手机历史上传、点赞等功能尚未全部完成，内容可用性仍受网络和上游状态影响。

**1.0.19：** 新增本人验证码登录与手机云片单只读查看；本地资料保持独立，退出应用后需要重新登录。优化收藏、历史、手机片单及离线文件的分区导航、搜索排序，以及播放器选集、画面适配和离线操作。以下旧版记录仅供追溯，不能视作当前版本说明。

1.0.15 在主搜索空白或临时错误时尝试官网备用检索，仅显示当前页匹配剧名，并明确标注范围有限；不把无关推荐当成匹配影片，也不虚构完整片库或后续分页。真实桌面三次搜索及详情打开、1080p播放/切集、1.0.14覆盖升级验收通过。

1.0.14 更新播放请求参数和视频信息解析，恢复桌面高清取流，未新增360p降级方案。四部剧实际横屏1920×1080、竖屏1080×1920均有声并持续播放；完整安装包的起播、切集、失败重试、倍速以及1.0.13覆盖升级验收通过。样本验收不代表所有剧集均已遍历验证。

1.0.13 修复视频加载失败，新增「设置 → 外观 → 黑暗模式」，切换立即生效并在重新打开后保留。更新安装后自动刷新红果桌面快捷方式，将旧版本入口迁移到当前安装版本。设置页移除后台运行提示条，仍可从托盘退出。

1.0.12 新增播放器“查找其他季”：打开候选列表、核对完整标题后手动选择，从该条目第 1 集开始；查找时保留播放，切换失败保留原媒体与已保存进度。更新下载显示已传输量和独立校验阶段；手动诊断摘要增加当前窗口的有限播放失败类别及数字状态码。选季是标题匹配，结果可能不完整；下载提示变化不代表提速。

1.0.11 改善暂停后的下一集准备、小窗更新提示与首页空片单/请求失败说明；设置增加使用帮助入口和手动生成/预览/复制本次运行诊断摘要。摘要不读旧日志或观看记录、不自动发送；可先查看再自行决定是否附到反馈中。服务未连接、播放中断等问题仍需按具体环境排查。

1.0.10 增加老板键隐藏暂停/恢复续播和3倍速；改善搜索与更新失败提示。更新下载在服务器支持且文件标识/范围核验通过时，尝试继续本次下载；关闭软件后不保留本次下载进度，不保证所有网络提速。安装包补齐作者署名和原发行入口，仍未配置 Windows 发布者代码签名。

1.0.9 增加选集分组与指定集数定位，服务检查进行中显示“正在检查”，改进整集进度、本机续看、缓冲与缓存回收；连播保留控制条闲置状态。剧集列表失败显示分类和HTTP状态码；内置签名服务使用系统分配的本机回环端口并核对所属进程，减少固定端口占用造成的启动失败；签名子进程退出时所属服务停止，再次检查连接可看到退出提示。本机诊断有大小上限且不自动上传。长片中断、服务未连接和特定环境的退出反馈仍在排查，不保证本次全部解决。旧版缓存可能在卸载后保留，请勿自行删除用户数据库。

1.0.4 支持删除单部观看历史或清空列表，并清除对应本机续播位置，收藏保留；改进播放控制栏显示、安装环境提示与本机服务端口选择。部分播放与跳转问题仍在排查。

v1.0.3 新增热播榜按需加载、播放服务未就绪时的明确提示，以及播放停滞后的手动重试入口；播放停滞原因仍在排查，重试不保证解决所有问题。

| 问题 | 已知状态与处理 |

| --- | --- |

| 默认播放清晰度 | 1.0.2 优先选择可识别的较高分辨率片源，避免仅按文件大小选择；实际清晰度取决于内容提供的片源，未新增手动画质切换。 |

| [切换下一集后倍速失效 #3](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/issues/3) | 1.0.1 已修复切换剧集后实际倍速可能恢复为 1 倍的问题。若更新后仍有问题，请补充系统、版本和步骤。 |

| [跨设备同步观看记录 #4](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/issues/4) | 1.0.2 的观看记录和收藏仅保存在当前电脑，尚不支持两台电脑或电脑与手机之间同步。已向提出者询问具体使用场景，暂无上线时间。 |

| [弹幕功能建议 #2](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/issues/2) | 已记录需求，暂未承诺支持或上线时间。 |

| [进度条显隐与外部播放器 #1](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/issues/1) | 原 Issue 已关闭；关闭记录没有关联修复提交，不能据此认定所有现象已经解决。相同问题可新建报告并附复现步骤。 |

## 使用反馈

- 遇到故障：[提交问题](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/issues/new?template=bug-report.yml)。请说明系统、软件版本、操作步骤、预期和实际结果。

- 有功能想法：[提出建议](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/issues/new?template=feature-request.yml)。先描述使用场景，方便判断改进方向。

- 不使用 GitHub 也可发邮件：[WaligoraAmodio288@gmail.com](mailto:WaligoraAmodio288@gmail.com)。如果愿意，也请说明在哪里看到本软件、是否成功播放或再次使用。

来源可以不填。请不要公开账号凭证、令牌、私人观看记录，截图时遮住无关个人信息。

## 下载与安装说明

当前版本尚未配置 Windows 发布者代码签名，系统可能显示未知发布者或 SmartScreen 提示。请核对下载来源与文件，不要关闭系统防护；某些系统策略可能限制安装。

Windows 1.0.28 安装器大小：`116996578` 字节。SHA-256：

```text

1bd6fb8be3cddb3419d0673d9259cac162a121cf3d5bd6e3ffd4474c73371c8f

```

摘要用于核对文件一致性，不能代替发布者身份认证。应用内更新使用固定公钥验证更新包签名；更新签名与 Windows 发布者代码签名不同。软件启动后可以检查版本，也可在设置中手动检查，仅在用户点击更新后下载安装。

[当前正式版说明与附件](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/latest) · [全部版本](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases)

## 关于本仓库

这是**公开发行与反馈仓库**，不包含私有应用源码或签名私钥，不代表应用源码已开源。Windows 版本保留安装器、更新签名、`latest.json`、摘要文件及本版本所需第三方对应源码附件；第三方许可、来源和声明也保留在安装目录 `backend/licenses`。

由渠道有数独立维护。相关品牌与内容归各自权利方所有，内容和播放可用性受来源及网络情况影响。

请核对原发行仓库账号为 `waligoraamodio288-rgb/hongguo-desktop-releases`。欢迎转载介绍并保留渠道有数署名与原版链接；第三方介绍或镜像请标明身份，避免读者误认开发和维护方。软件名称、截图或版权文字本身不能证明镜像文件未被修改，请对照原发行页同版本摘要。
