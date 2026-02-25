# 安装指南

本指南将详细介绍 Zotero PDF2zh 插件的安装步骤。

::: tip 开始之前
请确保您已安装：
- **Python 3.12.0** - [下载链接](https://www.python.org/downloads/)
- **Zotero 8** - [下载链接](https://www.zotero.org/download/)
:::

::: warning Windows 用户
请使用**管理员身份**打开命令提示符（cmd.exe）执行所有命令。
:::

---

## 选择您的系统

- **[Windows](#windows-安装)**
- **[macOS](#macos-安装)**
- **[Linux](#linux-安装)**
- **[Docker 部署](/zh/guide/docker)** - 推荐，环境隔离更好

---

## Windows 安装

### 1. 安装虚拟环境工具

**使用 uv（推荐）：**

```shell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

验证安装：
```shell
uv --version
```

### 2. 下载并解压 server

```shell
# 创建并进入项目文件夹
mkdir zotero-pdf2zh
cd zotero-pdf2zh

# 下载并解压 server 文件夹
curl -L -o server.zip https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/server.zip
tar -xf server.zip

# 进入 server 文件夹
cd server
```

### 3. 安装依赖并启动

```shell
# 安装依赖
pip install -r requirements.txt

# 启动服务
python server.py
```

::: tip 保持服务运行
翻译功能需要保持 `server.py` 运行状态，请不要关闭此窗口。
:::

---

## macOS 安装

### 1. 安装虚拟环境工具

**使用 uv（推荐）：**

```shell
wget -qO- https://astral.sh/uv/install.sh | sh
# 或使用 curl
curl -LsSf https://astral.sh/uv/install.sh | sh
```

验证安装：
```shell
uv --version
```

### 2. 下载并解压 server

```shell
# 创建并进入项目文件夹
mkdir zotero-pdf2zh && cd zotero-pdf2zh

# 下载并解压 server 文件夹
wget https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/server.zip
unzip server.zip

# 进入 server 文件夹
cd server
```

### 3. 安装依赖并启动

```shell
# 安装依赖
pip install -r requirements.txt

# 启动服务
python server.py
```

::: tip 保持服务运行
翻译功能需要保持 `server.py` 运行状态，请不要关闭此窗口。
:::

---

## Linux 安装

### 1. 安装虚拟环境工具

**使用 uv（推荐）：**

```shell
wget -qO- https://astral.sh/uv/install.sh | sh
# 或使用 curl
curl -LsSf https://astral.sh/uv/install.sh | sh
```

验证安装：
```shell
uv --version
```

### 2. 下载并解压 server

```shell
# 创建并进入项目文件夹
mkdir zotero-pdf2zh && cd zotero-pdf2zh

# 下载并解压 server 文件夹
wget https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/server.zip
unzip server.zip

# 进入 server 文件夹
cd server
```

### 3. 安装依赖并启动

```shell
# 安装依赖
pip install -r requirements.txt

# 启动服务
python server.py
```

::: tip 保持服务运行
翻译功能需要保持 `server.py` 运行状态。

如需后台运行：
```shell
nohup python server.py > server.log 2>&1 &
```
:::

---

## 安装 Zotero 插件

1. 下载最新插件：[v3.0.37](https://github.com/guaguastandup/zotero-pdf2zh/releases/download/v3.0.37/zotero-pdf-2-zh.xpi)

2. 在 Zotero 中打开「工具 → 插件」

3. 将下载的 xpi 文件拖入插件窗口进行安装

4. 如果功能未生效，请重启 Zotero

---

## 配置插件

1. 打开「工具 → PDF2zh 首选项」

2. 配置以下选项：
   - **Python Server IP**: 默认为 `http://127.0.0.1:8890`
   - **翻译引擎**: 选择 `pdf2zh` 或 `pdf2zh_next`
   - **LLM API**: 配置翻译服务（详见 [配置说明](/zh/guide/configuration)）

---

## 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--enable_venv` | `True` | 开启虚拟环境管理 |
| `--env_tool` | `uv` | 虚拟环境工具（uv/conda） |
| `--port` | `8890` | 服务端口 |
| `--check_update` | `True` | 自动检查更新 |

### 示例

```shell
# 切换端口
python server.py --port=9999

# 使用 conda
python server.py --env_tool=conda

# 关闭虚拟环境管理
python server.py --enable_venv=False
```

---

## 下载失败处理

如果下载 server.zip 失败，可以直接访问 [server.zip](https://github.com/guaguastandup/zotero-pdf2zh/blob/main/server.zip) 手动下载。

---

## 其他部署方式

除了直接安装，还有以下部署方式：

| 方式 | 说明 | 链接 |
|------|------|------|
| **Docker** | 环境隔离，适合服务器部署 | [查看 →](/zh/guide/docker) |
| **Homebrew** | 自动化管理，适合 macOS/Linux | [查看 →](/zh/guide/homebrew) |

---

## 下一步

- [配置说明](/zh/guide/configuration) - 插件和服务配置
- [翻译选项](/zh/guide/translation-options) - 各种翻译功能
- [常见问题](/zh/guide/faq/) - 遇到问题？
