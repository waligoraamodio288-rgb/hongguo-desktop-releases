# 深色外观、滚轮换集与 Windows Java 路径兼容性：维护者集成材料

这是针对 Windows 版 **1.0.12** 的贡献材料。公开仓库不含应用源码，因此这些文件需要维护者移入私有源码、构建并发布；合并此目录不会改变现有安装包，也不表示公开版已经包含这些改动。

## 深色外观

`theme-toggle.js` 提供“深色 / 浅色 / 跟随系统”，默认深色。选择保存在 `hongguo-local-theme`；存储被禁用时仍可切换。控制器在 `<html>` 设置 `data-local-theme`，并在设置页重新挂载后补回外观行。媒体颜色保持原样，没有对视频或封面使用反色滤镜。

| 文件 | 用途 |
| --- | --- |
| `theme-toggle.js` | 已在本机 1.0.12 验证的外观控制器；设置项使用中文标签和原生 select |
| `episode-wheel.js` | 在视频画面上滚轮向上上一集、向下下一集，复用现有换集按钮 |
| `generate_dark_css.py` | 从本地 CSS 生成仅在深色主题启用的颜色覆盖，保留规则顺序与透明/品牌色声明 |
| `dark-theme.css` | 画布、设置控件、导航强调色、焦点、滚动条的补充样式 |
| `windows_java_paths.py` / `desktop_bootstrap.patch` | Java 运行时路径适配器与最小启动器集成 diff |
| `tests/` | 前端使用自造 fixture；Java 测试可选接入本机 backend |

维护者集成步骤：

1. 在私有前端源码中加载外观控制器，建议将外观行移入现有设置组件，并把 observer 改为框架生命周期。保持 `hongguo-local-theme` 与 `data-local-theme`，避免用户偏好迁移丢失。
2. 把常用颜色逐步移到 `--ink`、`--muted`、`--paper`、`--line` 等源码级 token。需要先迁移既有十六进制样式时，可运行：

   ```powershell
   python -m pip install -r contributions/dark-mode-and-windows-java-paths/requirements.txt
   python contributions/dark-mode-and-windows-java-paths/generate_dark_css.py path/to/private-app.css path/to/dark-overrides.css
   ```

   加载顺序是原样式 → 生成的覆盖；输出已包含 `dark-theme.css`。不要把私有输入 CSS、原 JS bundle 或重打包可执行文件提交到本仓库。
3. 在首屏渲染前应用已保存的偏好，减少浅色闪烁。控制器在脚本执行时立即应用主题；脚本加载位置由私有构建决定。检查浅色恢复、系统主题变化、导航状态、弹窗、播放器和键盘焦点，再用正常构建发布。

生成器是迁移辅助工具：它处理传统规则中的十六进制颜色和 `@media` / `@supports` / `@layer`，保留 URL、字符串、图片与关键帧，排除登录二维码相关选择器；它不解析命名色、`rgb()`/`hsl()`/`oklch()`、CSS nesting 或复杂的主题变量语义。所有颜色覆盖都应由维护者审阅，不能代替全页面视觉验收。

## 滚轮换集

在视频画面上，向上滚动进入上一集，向下滚动进入下一集。一次连续滚动最多切换一集；正在加载或达到第一/最后一集时不排队。播放控制、进度条、倍速选择、可编辑内容和右侧选集列表保留原来的滚轮行为，组合键与横向滚动不会换集。

`episode-wheel.js` 不依赖前端框架，可在现有模块之后加载。它只在 `.player-stage` 的画布区域处理可取消的垂直 wheel，调用该 stage 内 `.player-toolbar button[aria-label="上一集"]` / `[aria-label="下一集"]` 的既有 click 行为；不复制私有播放器逻辑，也不绕过 disabled 状态。若改动了这些 DOM 接口，维护者需同步调整选择器。

控制器把 `deltaMode` 的像素、行、页统一成像素，积累 48px 后切换；240ms 没有新的有效滚轮事件才开始下一次手势。连续滚动的惯性与播放器重挂载不会导致多次换集。全局标记确保重复加载脚本也只有一个 document capture listener；listener 使用 `passive:false`，但只对视频画面上的有效事件取消默认滚动。若视频启用浏览器原生 controls，则完整保留其原生交互。

## Windows Java 路径兼容性

本机安装目录中的中文不能由系统 ANSI 代码页编码。原启动器执行内置 Java 时无法加载 `java.dll`；仅改用 8.3 短路径虽能运行 `java -version`，但 signer 的网络库会把路径还原成中文，随后加载 `net.dll` 时仍报 `UnsatisfiedLinkError`。这一现象属于本机服务启动，不能据此认定其他播放问题有相同根因。

`windows_java_paths.py` 在原 JRE 路径不兼容时，使用现有应用 data 目录下的 `runtime-links/jre` junction 启动同一份内置 JRE。它不移动或复制 JRE；已存在的别名必须指向同一目录，否则报错，并保留已有内容。该别名不依赖本次诊断工作目录。原 JRE 路径已兼容或非 Windows 时直接返回原路径。

维护者需把模块随 backend 打包，并将 `desktop_bootstrap.patch` 的三处新增/替换应用到私有启动器：导入 `java_runtime`、解析运行时目录、用解析后的 `bin/java.exe` 启动 signer。该 diff 以本机 1.0.12 启动器为参考；行号和私有源码可能不同，需核对后集成。保留原来的参数、Unicode 工作目录、动态端口和进程所有权检查。

应用 data 目录必须是绝对路径，且别名路径能由当前系统 ANSI 代码页编码；否则明确报错。本机修复不包含对所有代码页/用户目录的兼容性保证。Junction 由现有 PowerShell 创建，路径通过环境变量传递，不拼接到命令文本。升级或卸载时，应核对别名指向当前内置 JRE，再按应用自己的数据清理策略处理；不要递归删除 junction 指向的 JRE。

## 验证

本目录的测试使用 Python、tinycss2 与本机 Microsoft Edge（Playwright 的 `msedge` channel）。命令在本目录运行：

```powershell
python -m pip install -r requirements-test.txt
python -m unittest discover -s tests -v
```

24 项前端测试覆盖颜色作用域、alpha、声明顺序、条件规则、URL 和二维码保留，以及真实浏览器中的三种外观、保存/恢复、设置页重挂载、存储失败、视频/封面不加滤镜。9 项滚轮测试包括真实鼠标事件、细小增量、加载与端点保护、控制/侧栏原生滚动、修饰键与横向事件、行/页单位，以及播放器重挂载和重复脚本。测试页面是自造 fixture，不能据此声称私有 React/Rust 源码已集成。生成器另外已使用本机 1.0.12 CSS 与自造页面验证画布、控件、选中导航和媒体样式；私有输入/输出未提交。

5 项 Java 测试需要 Windows 上已集成此模块的 backend。未设置路径时会明确跳过；需要验证启动器时，在上述命令之前设置本机路径：

```powershell
$env:HONGGUO_TEST_BACKEND = 'C:\path\to\installed\backend'
```

这些测试运行内置 JVM、启动并停止测试自己创建的 signer、验证回环监听和错误别名保留，以及原启动器的 drive/UNC 路径规范化；不请求内容、不修改用户数据库。它们在本目录创建被 gitignore 排除的测试别名/标记，不能把这些文件作为提交材料。一次测试 signer 监听成功不等于端到端播放已验证。

本机实际应用的深色设置页另有截图；它验证的是本机修改后的 1.0.12。服务状态和端到端播放需要单独验证，不能由深色截图推断。

本机生产启动器另已验证：使用应用 data 目录中的持久 JRE 别名，Python/Java 子进程存活，API 静态入口返回 HTTP 200，signer 拥有本机回环监听。该结果验证服务启动修复；本次材料不据此宣称内容服务或端到端播放始终可用。

滚轮控制器也已装入本机应用并使用真实鼠标事件验证：当前集 → 下一集 → 原集，随后恢复播放位置与播放状态。实际设置页验证了浅色/深色切换、中文标签、原字体和“已连接”状态。
