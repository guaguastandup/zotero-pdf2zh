# 虚拟环境问题

关于 conda/uv 安装和虚拟环境管理的问题。

---

## 我不想使用虚拟环境管理，可以吗？

### 问题描述

我的 conda/uv 安装失败了，或者我不想使用虚拟环境管理，该怎么办？

### 原因

虚拟环境管理是推荐的安装方式，但不是必须的。如果您只使用 pdf2zh_next/pdf2zh 引擎中的一个，并且全局 Python 版本为 3.12.0，可以跳过虚拟环境管理。

### 解决方案

```shell
# 0. 安装 python3.12.0
# 0. 安装 uv（可选，参考指南中的 uv 安装教程）

# 1. 创建并进入 zotero-pdf2zh 文件夹
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
# 或者（如果已经安装了 uv）
uv tool install --python 3.12 pdf2zh-next

# 5. 执行脚本（关闭虚拟环境管理）
python server.py --enable_venv=False
```

::: tip 建议
即使不使用虚拟环境管理，建议依然安装 uv 或 conda，方便后续管理其他 Python 项目。
:::

---

## Failed to canonicalize script path

### 问题描述

命令行中提示：`Failed to canonicalize script path`

### 原因

虚拟环境路径与创建时的路径不一致，通常是因为移动了 server 文件夹或修改了文件夹名称。

### 解决方案

1. 删除 `server` 路径下的虚拟环境文件夹：
   - `zotero-pdf2zh-next-venv`（pdf2zh_next 的虚拟环境）
   - `zotero-pdf2zh-venv`（pdf2zh 的虚拟环境）

2. 重新运行 `python server.py` 重新创建虚拟环境

::: warning 注意
使用 uv 方法在安装配置后不可以修改路径名/移动文件夹，否则需要重新配置虚拟环境。
:::

---

## conda/uv 安装后命令不识别

### 问题描述

安装了 conda 或 uv 后，执行命令提示 "command not found" 或 "不是内部或外部命令"。

### 原因

安装路径没有添加到系统的环境变量（PATH）中。

### 解决方案

### uv 安装失败处理

如果 `uv --version` 检查失败，需要将 uv 执行路径添加到全局路径，并重启终端：

```shell
# MacOS/Linux
export PATH="$PATH:/Users/Username/.local/bin"

# Windows（临时）
$env:Path = "C:\Users\Username\.local\bin;$env:Path"

# Windows（永久，需手动设置）
# 1. 搜索"编辑系统环境变量"
# 2. 点击"环境变量"
# 3. 在"用户变量"中找到 Path，点击"编辑"
# 4. 添加 C:\Users\Username\.local\bin
```

::: warning 注意
请将 `Username` 替换为您自己的用户名。
:::

### conda 安装失败处理

重新安装 conda 或添加到 PATH：

```shell
# MacOS/Linux (添加到 ~/.bashrc 或 ~/.zshrc)
export PATH="$PATH:/path/to/conda/bin"

# Windows (同 uv 方法，添加 conda 的 bin 目录到 PATH)
```

---

## 预热安装卡住或失败

### 问题描述

使用 `--warmup` 参数预热时，安装过程卡住不动。

### 原因

预热过程需要从网络下载 babeldoc 的资源文件，包括字体和模型文件，文件较大，下载时间较长。

### 解决方案

1. **耐心等待** - 预热过程可能需要 5-15 分钟，取决于网络速度

2. **跳过预热** - 如果不想等待，可以使用非预热版本：
   ```shell
   # 不使用 --warmup，直接运行
   python server.py
   ```

3. **手动下载资源** - 如果网络问题导致下载失败：
   - 访问 [pdf2zh_next 最新 release](https://github.com/PDFMathTranslate/PDFMathTranslate-next/releases)
   - 下载其中的 exe 包（例如 `pdf2zh-v2.6.4-BabelDOC-xxx-with-assets-win64.zip`）
   - 解压后运行 pdf2zh.exe，打开 GUI 路径翻译一篇文章后退出
   - 回到插件重新翻译

---

## 如何在虚拟环境中手动安装包？

### 问题描述

需要手动进入虚拟环境安装或升级 Python 包。

### 原因

某些情况下需要手动管理虚拟环境中的包，比如降级 onnx 版本解决 DLL 错误。

### 解决方案

### 1. 进入虚拟环境

#### 使用 conda

```shell
conda activate zotero-pdf2zh-next-venv
# 或 pdf2zh 对应的环境
conda activate zotero-pdf2zh-venv
```

#### 使用 uv

**macOS/Linux:**
```shell
source ./zotero-pdf2zh-venv-next/bin/activate
# 或 pdf2zh 对应的环境
source ./zotero-pdf2zh-venv/bin/activate
```

**Windows:**
```shell
.\zotero-pdf2zh-next-venv\Scripts\activate
# 或 pdf2zh 对应的环境
.\zotero-pdf2zh-venv\Scripts\activate
```

### 2. 安装/升级包

```shell
# conda 环境
pip install --upgrade pdf2zh_next babeldoc

# uv 环境
uv pip install --upgrade pdf2zh_next babeldoc
```

### 3. 退出虚拟环境

```shell
deactivate
```
