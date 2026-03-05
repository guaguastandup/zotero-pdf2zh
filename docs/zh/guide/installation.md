# 安装指南

本指南将详细介绍 Zotero PDF2zh 插件的安装步骤。

::: tip 开始之前
请确保您已安装：
- **Python 3.12.0** - [下载链接](https://www.python.org/downloads/) | [安装教程（Windows）](https://www.bilibili.com/video/BV18q4y1R7gW/)
- **Zotero 7** 或 **Zotero 8** - [下载链接](https://www.zotero.org/download/)
:::

---

## 第零步：打开命令行工具

后续步骤中的指令都需要在命令行中执行。

### Windows 用户

1. 按 `Win + R`，输入 `cmd`，按回车
2. 或者在开始菜单搜索"cmd"或"命令提示符"
3. ⚠️ **请以管理员身份运行**：右键点击"命令提示符"，选择"以管理员身份运行"

::: warning Windows 用户注意
请勿在 C 盘（系统盘）下创建项目文件夹，建议在 D 盘或其他非系统盘操作。例如：先执行 `D:` 切换到 D 盘，再执行后续命令。
:::

### macOS 用户

1. 按 `Cmd + 空格`，输入"终端"或"Terminal"，按回车
2. 或者在"应用程序" → "实用工具" → "终端"

### Linux 用户

打开终端（通常快捷键为 `Ctrl + Alt + T`）

---

## 选择安装方式

- **[方式一：uv 安装（推荐）](#方式一uv-安装推荐)** - 快速、轻量
- **[方式二：conda 安装](#方式二conda-安装)** - 成熟稳定
- **[方式三：不使用虚拟环境](#方式三不使用虚拟环境)** - 简单直接
- **[其他部署方式](#其他部署方式)** - Docker、Homebrew、Windows exe

---

## 方式一：uv 安装（推荐）

### 第一步：安装 uv

```shell
# macOS/Linux
wget -qO- https://astral.sh/uv/install.sh | sh

# Windows（在 PowerShell 中执行）
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 第二步：验证 uv 安装

```shell
uv --version
```

如果显示版本号，则 uv 安装完成。

::: warning 安装失败处理
如果 `uv --version` 检查失败，需要将 uv 路径添加到 PATH 并重启终端：

```shell
# macOS/Linux
export PATH="$HOME/.local/bin:$PATH"

# Windows PowerShell
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
```
:::

### 第三步：下载并解压 server

```shell
# 创建并进入项目文件夹
mkdir zotero-pdf2zh && cd zotero-pdf2zh

# 下载并解压 server 文件夹
# macOS/Linux
wget https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/server.zip
unzip server.zip

# Windows
curl -L -o server.zip https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/server.zip
tar -xf server.zip

# 进入 server 文件夹
cd server
```

::: tip 下载失败？
如果 server.zip 下载失败，可以直接访问 [server.zip](https://github.com/guaguastandup/zotero-pdf2zh/blob/main/server.zip) 手动下载。
:::

### 第四步：安装依赖并启动

```shell
# 安装依赖
pip install -r requirements.txt

# 启动服务（使用 uv，默认选项）
python server.py
```

::: danger 重要提示
翻译功能依赖 Python 脚本，**需要保持脚本的运行状态**。只要您需要使用翻译功能，就**不要关闭这个 Python 脚本窗口**。关闭脚本后翻译功能将无法使用。
:::

---

## 方式二：conda 安装

### 第一步：安装 conda

参考官方文档安装：[Miniconda 安装指南](https://www.anaconda.com/docs/getting-started/miniconda/install#windows-command-prompt)

### 第二步：验证 conda 安装

```shell
conda --version
```

如果显示版本号，则 conda 安装完成。

### 第三步：下载并解压 server

同 [uv 安装 - 第三步](#第三步下载并解压-server)

### 第四步：安装依赖并启动

```shell
# 安装依赖
pip install -r requirements.txt

# 启动服务（指定使用 conda）
python server.py --env_tool=conda
```

---

## 方式三：不使用虚拟环境

如果您只使用 pdf2zh_next/pdf2zh 引擎中的一个，并且全局 Python 版本为 3.12.0，可以不使用虚拟环境管理。

```shell
# 1. 创建并进入项目文件夹
mkdir zotero-pdf2zh && cd zotero-pdf2zh

# 2. 下载并解压 server 文件夹
wget https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/server.zip
unzip server.zip

# 3. 进入 server 文件夹
cd server

# 4. 安装执行包
pip install -r requirements.txt
# 如果只使用 pdf2zh:
pip install pdf2zh==1.9.11 numpy==2.2.0
# 如果只使用 pdf2zh_next:
pip install pdf2zh_next

# 5. 执行脚本（关闭虚拟环境管理）
python server.py --enable_venv=False
```

---

## 安装 Zotero 插件

1. 下载最新插件：[v4.0.0](https://github.com/guaguastandup/zotero-pdf2zh/releases/download/v4.0.0/zotero-pdf-2-zh.xpi)

2. 在 Zotero 中打开「工具 → 插件」

3. 将下载的 xpi 文件拖入插件窗口进行安装

4. 如果功能未生效，请重启 Zotero

::: tip 自动更新
您可以在 Zotero 中检查更新，或选择自动更新，来获取最新版本插件。
:::

---

## 配置插件

1. 打开「工具 → PDF2zh 首选项」

2. 配置以下选项：
   - **Python Server IP**: 默认为 `http://127.0.0.1:8890`
   - **翻译引擎**: 选择 `pdf2zh` 或 `pdf2zh_next`
   - **LLM API**: 配置翻译服务（详见 [配置说明](/zh/guide/configuration)）

3. 点击"检查连接"按钮验证服务是否正常运行

---

## 默认配置说明

执行 `python server.py` 时的默认选项：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| 虚拟环境管理 | 开启 | 使用 `uv` 管理 |
| 自动安装依赖 | 开启 | 首次运行自动安装 |
| 自动检查更新 | 开启 | 启动时检查 |
| 更新源 | gitee | 国内用户友好 |
| 端口号 | 8890 | 服务端口 |
| 镜像源 | 中科大 | 加速包安装 |

---

## 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--enable_venv` | `True` | 开启虚拟环境管理 |
| `--env_tool` | `uv` | 虚拟环境工具（uv/conda） |
| `--port` | `8890` | 服务端口 |
| `--check_update` | `True` | 自动检查更新 |
| `--update_source` | `gitee` | 更新源（github/gitee） |
| `--enable_mirror` | `True` | 启用国内镜像 |
| `--mirror_source` | 中科大镜像 | 镜像源地址 |

### 常用示例

```shell
# 切换端口
python server.py --port=9999

# 使用 conda
python server.py --env_tool=conda

# 关闭自动检查更新
python server.py --check_update=False

# 切换更新源（如果 gitee 源更新失败）
python server.py --update_source="github"

# 关闭镜像加速
python server.py --enable_mirror=False

# 自定义镜像源
python server.py --mirror_source="https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/"
```

---

## 一键启动配置

每次翻译都需要打开终端执行 `python server.py`，您可以配置一键启动：

### Windows 用户 - 创建桌面快捷脚本

1. 在桌面新建一个文本文件，重命名为 `start-pdf2zh.bat`
2. 右键编辑，写入以下内容（请根据实际路径修改）：

```bat
@echo off
cd /d D:\zotero-pdf2zh\server
python server.py
pause
```

3. 保存后双击即可启动

### macOS / Linux 用户 - 配置别名

1. 打开终端，编辑 shell 配置文件：

```shell
# 如果使用 zsh（macOS 默认）
nano ~/.zshrc
# 如果使用 bash
nano ~/.bashrc
```

2. 在文件末尾添加别名（请根据实际路径修改）：

```shell
alias pdf2zh-start='cd /path/to/zotero-pdf2zh/server && python server.py'
```

3. 保存后执行：

```shell
source ~/.zshrc
# 或
source ~/.bashrc
```

4. 之后只需在终端输入 `pdf2zh-start` 即可一键启动

---

## 其他部署方式

| 方式 | 说明 | 适用场景 |
|------|------|----------|
| **[Docker](/zh/guide/docker)** | 环境隔离 | 服务器部署、多环境管理 |
| **[Homebrew](/zh/guide/homebrew)** | 自动化管理 | macOS/Linux 用户 |
| **Windows exe** | 无需配置环境 | Windows 用户，不想配置 Python |

### Windows exe 版本安装

如果您不想配置 Python 虚拟环境，可以直接使用 pdf2zh_next 提供的预编译 exe 版本。

**安装步骤：**

1. 下载 exe 包：访问 [pdf2zh_next Release](https://github.com/PDFMathTranslate/PDFMathTranslate-next/releases) 页面，下载 `pdf2zh-v2.x.x-BabelDOC-v0.x.x-win64.zip`（选择 `with-assets` 版本）

2. 解压文件：将下载的 zip 文件解压到 `server` 目录下
   - 解压后目录结构：`server/pdf2zh-v2.x.x-BabelDOC-v0.x.x-win64/pdf2zh/pdf2zh.exe`

3. 运行服务：
```shell
python server.py --enable_winexe=True --winexe_path='./pdf2zh-v2.x.x-BabelDOC-v0.x.x-win64/pdf2zh/pdf2zh.exe'
```

::: warning 注意事项
- exe 版本不需要配置 Python 虚拟环境
- 确保exe路径正确，路径相对于 `server` 目录
- 如果遇到 DLL 相关错误，请安装 [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)
:::

---

## 注意事项

- 如果使用 uv 方法安装，在安装后**请不要移动 server 文件夹，也不要修改文件夹名**
- 如果启动时更新检查失败，可以根据网络情况切换更新源

---

## 下一步

- [配置说明](/zh/guide/configuration) - 插件和服务配置
- [翻译选项](/zh/guide/translation-options) - 各种翻译功能
- [常见问题](/zh/guide/faq/) - 遇到问题？
