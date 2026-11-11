<!-- Copyright (c) 2026 kraynux - kraynux@proton.me - Licence MIT (voir fichier LICENSE) -->
<div align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/assets/omega-connect.png" alt="Omega-Connect" width="512">
</div>

# 🔗 OMEGA-CONNECT

**将 omega 套件中的应用程序相互关联，无论是在一台机器上还是在整个网络中**

> 由 [kraynux](https://github.com/kraynux) 为 [Omega-Server](https://kraynux.snake-mackarel.ts.net) 打造   

官方页面：[OMEGA-CONNECT](https://kraynux.snake-mackarel.ts.net/omega-connect/translation/zh-CN/) &nbsp; 预览：[截图](https://kraynux.snake-mackarel.ts.net/omega-connect/screenshots/)  

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](../../../LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Linux-informational.svg)](https://www.linux.org/)
[![Interface](https://img.shields.io/badge/Interface-TUI%20%2B%20Textual-cyan.svg)](https://github.com/Textualize/textual)

🌐 界面提供 **17 种语言** —— 参见[界面语言](#界面语言)。  
**语言：**  
<img src="https://flagcdn.com/w20/fr.png" alt="Français" style="height:14px;"> [Français](../../../README.md) · <img src="https://flagcdn.com/w20/gb.png" alt="English" style="height:14px;"> [English](../en/README.md) · <img src="https://flagcdn.com/w20/es.png" alt="Español" style="height:14px;"> [Español](../es/README.md) · <img src="https://flagcdn.com/w20/br.png" alt="Português (Brasil)" style="height:14px;"> [Português (Brasil)](../pt-BR/README.md) · <img src="https://flagcdn.com/w20/it.png" alt="Italiano" style="height:14px;"> [Italiano](../it/README.md) · <img src="https://flagcdn.com/w20/de.png" alt="Deutsch" style="height:14px;"> [Deutsch](../de/README.md) · <img src="https://flagcdn.com/w20/nl.png" alt="Nederlands" style="height:14px;"> [Nederlands](../nl/README.md) · <img src="https://flagcdn.com/w20/pl.png" alt="Polski" style="height:14px;"> [Polski](../pl/README.md) · <img src="https://flagcdn.com/w20/ru.png" alt="Русский" style="height:14px;"> [Русский](../ru/README.md) · <img src="https://flagcdn.com/w20/cn.png" alt="中文" style="height:14px;"> [中文](README.md) · <img src="https://flagcdn.com/w20/vn.png" alt="Tiếng Việt" style="height:14px;"> [Tiếng Việt](../vi/README.md) · <img src="https://flagcdn.com/w20/th.png" alt="ไทย" style="height:14px;"> [ไทย](../th/README.md) · <img src="https://flagcdn.com/w20/id.png" alt="Bahasa Indonesia" style="height:14px;"> [Bahasa Indonesia](../id/README.md) · <img src="https://flagcdn.com/w20/jp.png" alt="日本語" style="height:14px;"> [日本語](../ja/README.md) · <img src="https://flagcdn.com/w20/kr.png" alt="한국어" style="height:14px;"> [한국어](../ko/README.md) · <img src="https://flagcdn.com/w20/in.png" alt="हिन्दी" style="height:14px;"> [हिन्दी](../hi/README.md) · <img src="https://flagcdn.com/w20/ae.png" alt="العربية" style="height:14px;"> [العربية](../ar/README.md)

---

**Omega-connect** 是 `omega-` 套件的互连器：它会在本机以及您网络中的机器上找到已安装的 omega 应用程序（omega-serv、omega-fire、omega-jail……），显示哪些已相互关联、哪些没有，并补上缺失的部分 —— 始终先展示它将要做什么。一旦关联完成，即使 omega-connect 没有运行，这些应用程序也能相互找到。

<p align="center">
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/zh-CN/omega-connect/A.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/zh-CN/omega-connect/B.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/zh-CN/omega-connect/C.png" width="24%" />
  <img src="https://raw.githubusercontent.com/kraynux/kraynux/refs/heads/main/docs/translation/zh-CN/omega-connect/D.png" width="24%" />
</p>

## 1. 愿景与范围

omega 应用程序是为协同工作而设计的：omega-serv 的日志由 omega-jail 的 jail 读取，fail2ban 的封禁会汇入 omega-serv 的黑名单，omega-fire 则把这一切展示出来。但前提是文件放在正确的位置、拥有正确的权限，并且每个应用程序都知道其他应用程序在哪里。这正是 Omega-connect 负责的事情。

### Omega-connect 能做什么

- 找到本机上的 omega 应用程序（个人目录、systemd、OpenRC 或 runit 服务、`/srv`、omega-serv 的实例登记）以及其他机器上的应用程序（使用您的密钥通过 SSH 连接）。
- 维护一份**登记册**，记录所有机器上的所有应用程序及其版本和状态。
- 检查应用程序之间的每一个**关联**（jail 读取的日志、到黑名单的桥接、保护名单、fail2ban 中 omega-jail 的文件、身份卡、共享空间），并指出哪里有问题。
- **同步**：创建缺失的身份卡，并准备好应用程序相互发现所用的**共享空间**。
- **修复**：每一处偏差都交由拥有该文件的应用程序来纠正；绝不由 omega-connect 代劳。
- **更新或重新安装**网络中某台机器上版本过旧或安装不当的应用程序，来源为该应用程序的 GitHub Release（校验和已验证）。
- **从您的工作站**对网络中的机器进行操作：无需在那台机器上输入任何内容，它的密码只由它自己询问一次。
- 生成一份完整的**报告**（文本、JSON 或 HTML 页面）。

### Omega-connect 不做什么

- 它不替代任何应用程序：fail2ban、omega-fire、omega-jail 和 omega-serv 各司其职。
- 它从不改写其他应用程序的文件。
- 为了扫描网络中的机器，它不会在上面安装任何永久性的东西，也不会留下运行中的服务。
- 它从不询问 SSH 密码，也从不看到您的管理员密码。

## 2. 安装

### 前提条件

- Linux，Python 3.10+。
- 对于网络中的机器：基于密钥的 SSH 访问，并且这些机器上装有 Python 3.10+。
- 用于获取依赖项（以及从 GitHub 获取更新）的互联网连接。

### 安装

在归档包所在的目录中执行：

```bash
tar -xzf omega-connect-0.1.0.tar.gz
cd omega-connect/
./install.sh
```

`install.sh`：

1. 创建虚拟环境 `.venv`（不完整的 `.venv` 会被移到一旁并重新创建）。
2. 安装 omega-lib（套件的库，随归档包提供）和 omega-connect。
3. 使 `omega-connect.sh` 和 `install.sh` 可执行。
4. 将别名 `connect` 添加到 `~/.bashrc` 和 `~/.zshrc`（不会重复添加）。

所有步骤都不需要管理员权限。

### 更新

在**包含** `omega-connect/` 的目录中（绝不要在其内部执行：`tar` 会创建一个嵌套目录），将新的归档包解压覆盖，然后重新运行 `install.sh`。归档包不含任何本地数据（`var/`：机器登记册、设置、导出文件）：现有的内容都不会被覆盖。

```bash
tar -xzf omega-connect-<version>.tar.gz
cd omega-connect/
./install.sh
```

## 3. 使用

### 交互模式（TUI）

```bash
./omega-connect.sh
```

或者，如果已创建别名，运行 `connect`。

主菜单分为两列：

| 管理 | 维护 |
|---|---|
| **登记册** —— 所有机器上的所有应用程序、其版本和状态 | **修复** —— 列出所有问题，由您选择 |
| **扫描** —— 本机，以及添加网络中的机器 | **报告** —— 一份完整文档，可导出 |
| **关联** —— 哪些已关联，哪些未关联，以及其状态 | **设置** —— 语言、主题、文件夹、清除 |
| **同步** —— 在所有机器上关联应用程序 | **帮助** —— 每个菜单、其功能及详细说明 |
| **仪表盘** —— 总览 | **退出** |

典型流程：**扫描**（先扫描本机，再扫描您的其他机器，这些机器会根据您的 Unison 配置、`~/.ssh/config` 和 `known_hosts` 推荐给您）→ **登记册**（更新或重新安装旧版应用程序）→ **同步**（勾选，然后同步）→ 通过 **关联** 和 **仪表盘** 查看结果 → 如果仍有偏差，使用 **修复**。

每个操作都会先显示其计划；未经您同意，什么都不会执行。对于网络中的机器，界面会在操作期间让位给终端：由那台机器自己询问一次密码。

#### 键盘快捷键

| 按键 | 操作 |
|---|---|
| `↑` / `↓` | 在元素之间切换 |
| `Tab` / `Shift+Tab` | 在界面区域之间切换 |
| `Enter` / `Space` | 激活；勾选一行（同步） |
| `Esc` | 返回上一个界面 |
| `a` | 帮助 |
| `s` | 设置 |
| `t` | 下一个主题 |
| `r` | 重绘界面 |
| `q` | 退出（需确认） |
| `Ctrl+P` | 命令：主题、截图、退出 |

### 状态

| 应用程序 | 关联 |
|---|---|
| ● 已关联 —— 已在共享空间中，且为最新 | OK |
| ◐ 已登记 —— 已有身份卡，但尚未进入共享空间 | 待修复 |
| ○ 已检测到 —— 没有身份卡 | 待修复（阻断性） |
| ▲ 待修复 —— 存在偏差 | 不存在 —— 无需关联 |
| ◌ 旧版本 —— 需要更新 | 无法验证 |
| ◇ 安装未完成 —— 需重新安装 | |
| ✕ 无法连接 —— 机器不再响应 | |

### 界面语言

界面提供 17 种语言：法语、英语、西班牙语、葡萄牙语（巴西）、意大利语、德语、荷兰语、波兰语、俄语、简体中文、越南语、泰语、印尼语、日语、韩语、印地语和阿拉伯语。语言在设置中选择（“Langue / Language”，该标签从不翻译），并在界面重启后生效；变量 `OMEGA_CONNECT_LANG`（例如 `OMEGA_CONNECT_LANG=en ./omega-connect.sh`）可在一次会话中强制使用某种语言。在 Linux 文本控制台（TTY）上，非拉丁文字的语言在该会话中以英语显示。命令行保持法语。

### 联系与支持

帮助（`a` 键）提供 **联系与支持** 界面：*请我喝杯咖啡*（开发者的 PayPal 页面）、*联系支持*（明文显示的邮箱地址和网站的联系表单）、*登记为用户（匿名）* 以及 *检查更新*。登记是自愿的，默认关闭，且只发送一次：仅用于统计用户数量，以及（如您愿意）其所在的大洲或国家（封闭列表，绝无自由文本）。它发送一个随机生成的密钥、软件名称（`omega-connect`）及其版本；绝不发送姓名、机器名、地址或设置。IP 地址不会记录在登记中，但与任何访问一样，会经过接收服务器的安全检查和日志。可随时在同一界面撤回。检查更新只读取已发布版本的列表，并且必须点击才会进行。

### 可脚本化模式（CLI）

任何命令都会触发命令行模式：

```bash
# 本机的应用程序，或网络中某台机器的应用程序（使用您的密钥通过 SSH）
./omega-connect.sh scanner
./omega-connect.sh scanner moi@192.168.1.109

# 关联本机的应用程序，或网络中某台机器的应用程序
./omega-connect.sh synchroniser
./omega-connect.sh synchroniser --machine moi@192.168.1.109

# 更新网络中某台机器上版本过旧的应用程序（GitHub Release）
./omega-connect.sh mettre-a-jour --machine moi@192.168.1.109

# 修复：本机，或网络中的某台机器
./omega-connect.sh reparer --machine moi@192.168.1.109

# 每个关联的状态，以及完整报告
./omega-connect.sh verifier
./omega-connect.sh rapport --format html --enregistrer
```

`--simulation` 只显示计划而不执行任何操作；`--oui` 不经询问直接执行；`--toutes-machines` 依次处理所有已知机器。

## 4. 网络中的机器

- **连接：** 仅使用您的密钥通过 SSH 连接；遵循 `~/.ssh/config`（别名、端口、用户）。受口令保护的密钥必须先加载到 SSH agent 中。
- **首次连接：** 在一切操作之前先显示该机器密钥的指纹；密钥发生变化的机器会被拒绝。
- **扫描：** 程序以只读方式发送到内存中；不安装、不写入任何内容，也不询问任何密码。
- **操作**（同步、修复、更新）：一个临时的私有目录接收程序以及（如有需要）归档包；结束时会被删除。管理员密码由那台机器自己询问一次。
- **身份：** 机器通过其系统标识符的指纹来识别，而不是通过地址：即使通过两个网络访问，它仍然是同一台机器。
- **更新：** 来源为每个应用程序的 GitHub Release；归档包的校验和在发送前用 `sha.txt` 验证，然后在机器上再次验证。每个应用程序都按照其 README 中“更新”一节的说明进行安装。

## 5. 身份卡与共享空间

- **身份卡：** 每个 omega 应用程序在安装时都会写入一个小文件，说明它是谁（应用程序、版本、标识符、机器）。所有人可读，其他账户永远无法修改。
- **共享空间：** `/var/lib/omega-synchro`，仅限 `omega-synchro` 组使用，只有管理员可以写入。Omega-connect 会把每个应用程序的身份卡和描述复制到其中；即使 omega-connect 没有运行，应用程序也能在这里相互找到。
- **共享空间的登记册：** omega-connect 创建的所有内容都会记录在其中；移除操作只撤销其中记录的内容，未知文件绝不会被删除。

## 6. 安全

- 启动时不提权：omega-connect 以您的账户运行；sudo 按操作逐一请求，并事先显示命令。
- 纠正由拥有该文件的应用程序完成（omega-jail 负责它放入 fail2ban 的内容，omega-serv 负责其 `var/` 的权限，每个应用程序负责自己的身份卡）。
- 如果某个应用程序可能在没有终端的情况下询问密码，则不会启动它。
- 搜索绝不跟随符号链接，不会跨越文件系统，并会忽略网络挂载。
- 导出和截图文件夹的清除会拒绝系统文件夹、个人文件夹以及 omega-connect 自身的文件夹。

## 7. 导出

- **报告**：所有机器的总结、剩余待办事项的精确列表、登记册、网络中的机器、每台机器的关联、共享空间。文本、JSON 或 HTML 页面（主题可选）。
- **帮助**：可导出为 HTML 页面。
- **截图**：`Ctrl+P` →“截图”（SVG）。
- 默认文件夹：omega-connect 目录下的 `var/exports/` 和 `var/screenshots/`，可在设置中修改。

## 8. 架构

整洁架构（Clean Architecture），与套件的其余部分一致：`domain/`（纯规则）、`application/`（用例）、`ports/`、`infrastructure/`（SSH、文件、GitHub、剪贴板）、`interfaces/`（命令行和 Textual 界面）、`app/`（组装）。依赖始终指向内部，由 `import-linter` 检查。应用程序之间共享的契约（身份卡、描述、共享空间）位于 `omega-lib` 中。

## 9. 测试

```bash
source .venv/bin/activate
lint-imports        # 检查依赖规则
pytest -q
ruff check src tests
mypy src
```

测试绝不触及真实的 `var/`，也不接触网络或 sudo：使用在本地执行的模拟 SSH、模拟 GitHub 和临时目录。

## 10. 范围之外

- 替代 fail2ban、omega-fire 或 omega-jail。
- 持续监控（没有常驻服务）。
- 首次在网络中的某台机器上安装 omega 应用程序。
- Web 仪表盘。

## 许可证

MIT —— 参见 [LICENSE](../../../LICENSE)。

---

> Omega-connect —— 查找、关联、修复。
> omega 应用程序彼此对话；omega-connect 确保它们能够做到。
