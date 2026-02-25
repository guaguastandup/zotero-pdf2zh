# 环境配置问题

关于 DLL 错误、路径配置、Python 版本等问题。

---

## 动态链接库(DLL)初始化例程失败 🔥

### 问题描述

出现错误："动态链接库(DLL)初始化例程失败"，或英文错误 "DLL initialization routine failed"。

### 原因

缺少必要的 Visual C++ 运行库，或 onnx 版本与系统不兼容。

### 解决方案

### 方案 1：降级 onnx 版本

进入对应的虚拟环境，将 onnx 包降级到 `1.16.1` 版本。

**pdf2zh 对应的虚拟环境名为 `zotero-pdf2zh-venv`**

**pdf2zh_next 对应的虚拟环境名为 `zotero-pdf2zh-next-venv`**

#### 使用 conda

```shell
# 进入虚拟环境
conda activate zotero-pdf2zh-next-venv

# 降级 onnx
pip install onnx==1.16.1
```

#### 使用 uv

**macOS/Linux:**
```shell
# 进入虚拟环境
source ./zotero-pdf2zh-venv-next/bin/activate

# 降级 onnx
pip install onnx==1.16.1
```

**Windows:**
```shell
# 进入虚拟环境
.\zotero-pdf2zh-next-venv\Scripts\activate

# 降级 onnx
pip install onnx==1.16.1
```

::: tip 不会操作？
如果您依然不会操作，可以把这段内容发送给 AI，并告诉它您正在使用 uv 还是 conda 进行虚拟环境管理。
:::

### 方案 2：安装 Visual C++ 运行库

下载并安装 Microsoft Visual C++ Redistributable：

1. **x64 版本**：[vc_redist.x64.exe](https://aka.ms/vs/17/release/vc_redist.x64.exe)
2. **x86 版本**：[vc_redist.x86.exe](https://aka.ms/vs/17/release/vc_redist.x86.exe)

::: tip 缺少哪个版本？
- 如果您已经安装了 x64 版本但依然报错，可能缺少的是 x86 版本
- 可以加入 QQ 群下载群文件中的 3 个 exe 包
:::

### 方案 3：macOS 旧版本系统

如果您正在使用 macOS 旧版本系统（这个问题大部分发生在 Windows 系统中），需要在安装时 Python 虚拟环境指定为 **3.11** 而不是 3.12。

### 方案 4：其他方法

群友贡献的解决方案：

![onnx 解决方案](https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/images/onnx-solution.png)

---

## Python 版本不兼容

### 问题描述

提示 Python 版本不兼容或某些功能无法正常工作。

### 原因

项目要求 Python 3.12.0 版本，使用其他版本可能导致兼容性问题。

### 解决方案

1. **检查当前 Python 版本**
   ```shell
   python --version
   # 或
   python3 --version
   ```

2. **安装 Python 3.12.0**
   - 前往 [Python 官网](https://www.python.org/downloads/)
   - 下载并安装 Python 3.12.0 版本

3. **macOS 旧版本系统**
   - 如果是 macOS 旧版本，可以尝试使用 Python 3.11
   - 在创建虚拟环境时指定 Python 版本

4. **使用虚拟环境指定版本**
   ```shell
   # conda
   conda create -n zotero-pdf2zh-next-venv python=3.12

   # uv
   uv venv --python 3.12
   ```

---

## 插件与 Zotero 版本不兼容

### 问题描述

插件安装后无法正常工作或 Zotero 提示不兼容。

### 原因

插件版本与 Zotero 版本不匹配。

### 解决方案

1. **确认 Zotero 版本**
   - 插件目前支持 Zotero 7 和 Zotero 8
   - Zotero 8 适配由 @[Aphcity](https://github.com/Aphcity) 完成

2. **下载正确的插件版本**
   - 最新版本：[v3.0.37](https://github.com/guaguastandup/zotero-pdf2zh/releases/download/v3.0.37/zotero-pdf-2-zh.xpi)
   - 旧版本 v2.4.3 可能存在兼容性问题

3. **在 Zotero 中检查更新**
   - 打开「工具 → 插件」
   - 点击"检查更新"按钮

---

## 路径包含中文或特殊字符

### 问题描述

安装或运行时出现与路径相关的错误。

### 原因

项目路径包含中文、空格或特殊字符，可能导致 Python 或其他工具无法正确识别路径。

### 解决方案

1. **避免使用中文路径**
   - 建议将项目放在纯英文路径下
   - 例如：`C:\Users\Username\zotero-pdf2zh` 而不是 `C:\Users\用户名\我的文件\zotero-pdf2zh`

2. **避免使用空格**
   - 路径中尽量不要包含空格
   - 如果必须包含空格，请用引号包裹路径

3. **重新创建项目**
   ```shell
   # 在英文路径下重新创建
   cd C:\Users\Username\
   mkdir zotero-pdf2zh && cd zotero-pdf2zh
   # 然后按照安装指南继续
   ```

---

## 权限问题

### 问题描述

安装或运行时提示权限不足（Permission denied）。

### 原因

1. Windows 用户未使用管理员身份运行 cmd
2. 文件或文件夹权限设置不当
3. macOS/Linux 需要执行权限

### 解决方案

### Windows

1. **使用管理员身份打开 cmd**
   - 搜索 "cmd"
   - 右键选择"以管理员身份运行"

2. **检查文件夹权限**
   - 右键文件夹 → 属性 → 安全
   - 确保当前用户有完全控制权限

### macOS/Linux

1. **添加执行权限**
   ```shell
   chmod +x install-with-uv.sh
   chmod +x install-with-conda.sh
   ```

2. **使用 sudo（如果必要）**
   ```shell
   sudo pip install -r requirements.txt
   ```

::: warning 警告
使用 sudo 需要谨慎，建议先尝试不使用 sudo 的方式。
:::

---

## 镜像源配置问题

### 问题描述

使用国内镜像源时安装失败或速度很慢。

### 原因

1. 镜像源地址配置错误
2. 镜像源暂时不可用
3. 网络连接问题

### 解决方案

1. **使用默认镜像**
   - 项目默认使用中科大镜像源
   - 如果有问题，可以尝试关闭镜像：
     ```shell
     python server.py --enable_mirror=False
     ```

2. **切换镜像源**
   ```shell
   # 使用清华镜像
   python server.py --mirror_source="https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/"

   # 使用阿里云镜像
   python server.py --mirror_source="https://mirrors.aliyun.com/pypi/simple/"
   ```

3. **使用预热脚本时的镜像选项**
   ```shell
   # 不使用镜像
   ./install-with-uv.sh --no-mirror
   ```
