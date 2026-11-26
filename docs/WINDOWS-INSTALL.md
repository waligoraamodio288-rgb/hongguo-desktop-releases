# 红果短剧电脑版下载与安装｜红果桌面端 Windows 指南

[打开 Windows 固定最新版](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/latest) · [项目首页](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases) · [反馈安装或播放问题](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/issues/new?template=bug-report.yml)

红果桌面端是「渠道有数」独立维护的免费第三方客户端。Windows 10 / 11 x64 电脑无需安卓模拟器，可以找剧、选集、收藏和从本机历史继续观看。下载时请核对发行仓库账号 `waligoraamodio288-rgb/hongguo-desktop-releases`。

## 首次安装，选哪个文件？

1. 打开固定最新版页面，点发行说明顶部的 Windows 安装包链接。若页面上没有直链，可展开 **Assets**（附件）。
2. 确认下载的文件名以 `-setup.exe` 结尾，再手动安装。
3. 运行安装程序。打开软件后，继续看[首次使用步骤](#装好后怎么在电脑上开始看)。

[深色模式、自动连播和版本查看](#看片设置怎么改)

## 装好后，怎么在电脑上开始看？

1. 在搜索框输入剧名，打开搜索结果中的剧集详情。
2. 选择一集，确认画面和声音正常。需要接着看时，回到左侧“历史”打开刚才的剧。
3. 如果卡住，可先对照下方的[安装或播放遇到问题](#安装或播放遇到问题)。需要反馈时，请注明卡在安装、打开软件、搜索或播放中的哪一步，并附上屏幕提示。

## 普通小窗和悬浮小电视怎么搭配？

播放一集后，在播放器工具栏里选择其中一个入口。

- **迷你窗口**：缩成桌面置顶小窗，继续播放当前一集。
- **悬浮小电视**：收起时只显示小电视。鼠标移入展开续播，移出即暂停并收回。
- **想切回持续播放**：如果从迷你窗口开启悬浮小电视，点「返回普通小窗」即可回到原来的小窗。

[查看 Windows 1.0.67 更新与下载](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/tag/v1.0.67)

## 看片设置怎么改？

打开 [Windows 1.0.66 的 24 秒设置实录](https://www.bilibili.com/video/BV1bbs86wEGt/)，按下表找对应画面。

| 想做的事 | 操作 | 视频位置 |
| --- | --- | --- |
| 晚上看剧时把界面调暗 | 设置 → 外观 → 打开「黑暗模式」。 | 00:00–00:10 |
| 看完一集先停下来 | 在设置中找到「自动播放下一集」，把开关关掉。同一区域也可设置默认倍速。 | 00:10–00:20 |
| 确认目前装的是哪一版 | 设置 → 关于，查看当前版本。 | 00:20–00:24 |

## 电脑上已经装过，怎样升级？

先到“设置 → 关于”检查更新。需要手动覆盖安装时，从 Windows 通知区域的托盘菜单完全退出旧程序，再运行此页链接下的最新版安装包，沿用原安装目录。

想长期跟进版本，可以把[发行订阅（Atom）](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases.atom)添加到 RSS 阅读器。订阅涵盖项目各平台的发行说明，Windows 安装包仍从固定最新版选择。

## 安装或播放遇到问题

| 遇到的情况 | 可以先做什么 |
| --- | --- |
| 看到了多个附件 | 手动安装选择 `-setup.exe`。同页的 `-update.exe` 供应用更新使用。 |
| 提示缺少 WebView2，或安装一直卡在补装 WebView2 | 先等补装完成。补装失败，或电脑已有 WebView2 但仍卡在补装步骤时，可从 [微软 WebView2 官方页面](https://developer.microsoft.com/microsoft-edge/webview2/)选择 Evergreen Standalone Installer（x64）安装或更新运行时。完成后重新运行红果 Setup。已安装红果的用户可直接重开应用。 |
| 安装程序退出并报告 `1603` | 如果同时提示 WebView2，按上一行补装或更新后再试。单靠 `1603` 无法确定原因。仍失败时，请保留安装提示，反馈 Windows 版本、红果安装包版本和安装停在哪一步。 |
| Windows 显示未知发布者 | 当前安装包没有 Windows 发布者代码签名。可按[原版安装包核对步骤](#从转载或镜像下载的安装包怎么核对)比对文件，保留系统防护。 |
| 提示播放服务未就绪 | 等待约一分钟，再到“设置 → 播放服务”点“检查连接”。仍未连接时，从托盘退出并重开后再查。 |
| 点了「立即播放」仍未出画，或某集播放中断 | 按下方步骤区分[首次未出画与开始后中断](#播放中断先排查哪一步)，再用同剧另一集和另一部剧对照。 |

## 从转载或镜像下载的安装包怎么核对？

1. 如果还没安装，可以直接从 [Windows 固定最新版](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/latest) 下载。转载和镜像页面显示的版本可能比 GitHub 旧。
2. 如果已经下载，可以从[原发行仓库的版本列表](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases)打开安装包文件名对应的版本，查看该版本的 `SHA256SUMS.txt`。在 PowerShell 中运行下面这条命令，把示例路径换成手上的文件完整路径。

   ```powershell
   Get-FileHash -Algorithm SHA256 -LiteralPath 'C:\路径\实际下载的安装包.exe'
   ```

3. 比对命令输出的 `Hash` 与摘要文件中同名 `-setup.exe` 那一行。两边相同可以核对文件与原发行一致。找不到对应文件或摘要不符时，从固定最新版重新下载。

## 播放中断先排查哪一步？

1. **按钮不可点击，或一直显示“播放准备完成后自动开始”。** 先到「设置 → 播放服务」检查连接，记下结果，回到剧集详情后再试一次。如果显示“读取剧集列表失败”，请同时记下画面上的错误提示和 HTTP 状态码（若有）。
2. **已经出画后卡住、断网中断或切集失败。** 先确认网络已恢复。界面提供「重试」或「重试当前集」时可以试一次。
3. **问题仍在。** 先对照同一部剧的另一集，再对照另一部剧，记录哪些能出画。然后在「设置 → 关于」核对当前版本。如果装的是旧版，可从[固定最新版](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/latest)覆盖升级后复测。提交反馈时，请附 Windows 和红果版本、剧名与集数、是否曾出画、提示原文和对照结果。可以先保留现有安装和本机记录。

## 发给第一次安装的朋友

> 在 Windows 10/11 x64 电脑上找短剧、选集和接着上次看。这里有下载、安装和第一次打开后的操作步骤：https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/blob/main/docs/WINDOWS-INSTALL.md

已经用过的朋友可直接打开[固定最新版](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/latest)。Mac 和 Android TV 请从[项目首页的设备下载入口](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases#按设备选择下载)选包。
