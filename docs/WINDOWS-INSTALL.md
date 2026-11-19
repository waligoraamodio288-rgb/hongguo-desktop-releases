# 红果电脑版下载与安装｜Windows 10 / 11 x64

[打开 Windows 固定最新版](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/latest) · [项目首页](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases) · [反馈安装或播放问题](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/issues/new?template=bug-report.yml)

红果桌面端是渠道有数独立维护的免费第三方客户端。可在电脑上找剧、选集、收藏和接着本机进度看。此页适用于 Windows 10 / 11 的 x64 电脑。

## 首次安装，选哪个文件？

1. 打开固定最新版页面，展开 **Assets**（附件）。
2. 下载文件名以 `-setup.exe` 结尾的 Windows 安装包。这个文件用于手动安装。
3. 运行安装程序。打开软件后，继续看[首次使用步骤](#装好后怎么在电脑上开始看)。

[看 24 秒设置实录](https://www.bilibili.com/video/BV1bbs86wEGt/)：从 1.0.66 界面查看版本、切换深色模式和调整自动连播。

## 装好后，怎么在电脑上开始看？

1. 在搜索框输入剧名，打开搜索结果中的剧集详情。
2. 选择一集，确认画面和声音正常。需要接着看时，回到左侧“历史”打开刚才的剧。
3. 如果卡住，可先对照下方的[安装或播放遇到问题](#安装或播放遇到问题)。需要反馈时，请注明卡在安装、打开软件、搜索或播放中的哪一步，并附上屏幕提示。

## 电脑上已经装过，怎样升级？

先到“设置 → 关于”检查更新。需要手动覆盖安装时，从 Windows 通知区域的托盘菜单完全退出旧程序，再运行此页链接下的最新版安装包，沿用原安装目录。

## 安装或播放遇到问题

| 遇到的情况 | 可以先做什么 |
| --- | --- |
| 看到了多个附件 | 手动安装选择 `-setup.exe`。同页的 `-update.exe` 供应用更新使用。 |
| 提示缺少 WebView2，或安装一直卡在补装 WebView2 | 先等待安装程序完成补装。如果补装失败，可从 [微软 WebView2 官方页面](https://developer.microsoft.com/microsoft-edge/webview2/)选择 Evergreen Standalone Installer（x64）。补装完成后，如果红果安装尚未完成，请重新运行红果 Setup。已安装的用户可直接重新打开红果。 |
| Windows 显示未知发布者 | 当前安装包没有 Windows 发布者代码签名。先核对原发行仓库和同版本 `SHA256SUMS.txt`，保留系统防护。 |
| 提示播放服务未就绪 | 等待约一分钟，再到“设置 → 播放服务”点“检查连接”。仍未连接时，从托盘退出并重开后再查。 |
| 某集播放中断 | 先重试一次，再换一部剧对照。按下方步骤记录[播放中断发生在哪一步](#播放中断先排查哪一步)。 |

## 播放中断先排查哪一步？

1. **还没进入播放器。** 如果详情页的播放按钮不可点击，先到「设置 → 播放服务」检查连接，并记下页面提示。
2. **已经进入播放器。** 记录是点播放后立刻中断，还是已经播了一段时间。点一次「重试当前集」，再换一部剧看是否也会中断。
3. **问题仍在。** 在「设置 → 关于」查看当前版本。请在问题反馈里写明 Windows 版本、红果版本、剧名与集数、故障发生的时点和两次测试结果。遇到中断时可以先保留现有安装和本机记录。

## 发给第一次安装的朋友

> 在 Windows 10/11 x64 电脑上找短剧、选集和接着上次看。这里有下载、安装和第一次打开后的操作步骤：https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/blob/main/docs/WINDOWS-INSTALL.md

已经用过的朋友可直接打开[固定最新版](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases/releases/latest)。Mac 和 Android TV 请从[项目首页的设备下载入口](https://github.com/waligoraamodio288-rgb/hongguo-desktop-releases#按设备选择下载)选包。
