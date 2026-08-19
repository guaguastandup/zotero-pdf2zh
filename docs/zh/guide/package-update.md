# 翻译环境安装与更新

Zotero PDF2zh v4.1.0 将 **Server/插件源码更新** 与 **Python 翻译环境更新** 分开处理，并为 Python 环境增加了 staging 安装与回滚保护。

## 新用户

新用户无需手工安装 BabelDOC、PyMuPDF 或指定 `pdf2zh_next` 的具体版本。

第一次真正使用 `pdf2zh_next` 时，Server 会：

1. 创建独立的 staging 虚拟环境；
2. 检测 PyPI、USTC、TUNA、阿里云等下载源；
3. 验证实际 distribution 文件可以下载；
4. 让 uv/pip 解析完整依赖；
5. 在 v4.1.0 支持的 `pdf2zh_next >= 2.9.0,<3.0.0` 范围内安装当前最新兼容版本及其依赖；
6. 检查依赖完整性和 CLI 入口；
7. 对 `pdf2zh_next` 额外确认 DeepSeek V4 thinking 参数可用；
8. 全部通过后，才将 staging 环境切换为正式环境。

这里故意限制在 `pdf2zh_next 2.x`。未来如果上游发布 3.x，已经发布出去的 v4.1.0 不会在未经验证的情况下自动跨 major 升级；需要由后续 Zotero PDF2zh 版本验证并放开支持范围。

如果任何步骤失败，不会留下一个被 Server 当作正常环境使用的“半安装”正式环境。Server 本身仍然可以启动，用户可以稍后重试。

## 已有用户升级到 v4.1.0

如果 Server 检测到已经存在 `pdf2zh_next` 环境，首次启动当前 Server 版本时会询问是否安全检查并更新：

```text
🔄 检测到已有 Python 翻译环境
当前 pdf2zh_next: ...

[Y] 安全检查并更新（推荐）
[N] 暂不更新

选择 [Y/n]:
```

直接回车等同于选择 `Y`。

选择更新后，**不会在当前正在工作的虚拟环境里直接执行 upgrade**。Server 会先创建新的 staging 环境，安装并验证成功后再切换。

因此：

- 更新成功：切换到新环境，并保留旧环境备份；
- 下载失败：旧环境不被修改；
- 依赖解析失败：旧环境不被修改；
- staging 安装失败：旧环境不被修改；
- 运行时验证失败：旧环境不被修改；
- 环境切换异常：尝试恢复旧环境。

即使更新失败，Server 仍会继续使用原有环境启动。旧环境不支持的新功能会在真正使用时给出明确提示。

如果选择 `N`，当前 Server 版本不会反复询问；之后仍可随时手工更新。如果用户选择更新但本次更新失败，同一 Server 版本也不会每次启动都重复弹出，可稍后主动运行 `python update_packages.py` 重试。

## 手工一键更新

进入 `server` 目录：

```shell
python update_packages.py
```

这是普通用户需要记住的唯一维护命令。它会自动沿用已有 uv/conda 环境；没有已有环境时优先使用 uv。

它和 Server 启动时的安全更新使用同一套事务流程：

```text
staging 环境
    ↓
网络与依赖检查
    ↓
安装
    ↓
运行时验证
    ↓
成功才切换
```

用户不需要自己判断 BabelDOC、PyMuPDF、pypdf 等版本。

### 自定义镜像或超时

```shell
python update_packages.py \
  --index-url "https://pypi.tuna.tsinghua.edu.cn/simple"

python update_packages.py --network-timeout 8
```

如果要强制指定环境管理工具：

```shell
python update_packages.py --env-tool uv
python update_packages.py --env-tool conda
```

## 高级诊断

### 检查下载网络

```shell
python manage_packages.py network
```

该操作只检测网络，不修改环境。测试源包括：

- PyPI
- USTC
- TUNA
- 阿里云

检测不仅访问索引，还会读取一个真实 distribution 文件的小片段。

### 查看当前版本

```shell
python manage_packages.py status
```

### 高级安全更新

```shell
python manage_packages.py update
```

高级更新现在同样使用 staging 环境，不再存在单独的原地升级路径。

## “最新版”的含义

更新工具不会使用 `--no-deps` 绕过上游依赖约束。

因此这里的“更新”准确含义是：

> **安装当前 Zotero PDF2zh 支持范围和上游依赖声明共同允许的最新兼容组合。**

对于 v4.1.0，`pdf2zh_next` 的托管范围是 `>=2.9.0,<3.0.0`。同时，不保证 BabelDOC、PyMuPDF 等每一个独立组件都达到各自的绝对最新版本。如果上游依赖元数据不允许某个组合，Zotero PDF2zh 不会强制安装它。

## DeepSeek V4 Thinking

DeepSeek V4 显式 Thinking 控制要求实际执行的 `pdf2zh_next` 支持：

```text
--deepseek-thinking-mode
--deepseek-reasoning-effort
```

v4.1.0 的新安装要求 `pdf2zh_next >= 2.9.0,<3.0.0`，并且安装后还会通过已安装 distribution 的静态 metadata/source 检查 runtime capability；不会为了检查能力启动 `pdf2zh_next --help`。

如果已有用户拒绝更新，仍然可以继续使用旧环境已有功能；但当使用 DeepSeek V4 时，如果实际运行时不支持 Thinking 控制，Server 会在任何翻译 API 请求之前停止，避免设置被忽略而产生额外费用。

## 配置文件升级

v4.1.0 不再每次启动都用 `.example` 覆盖现有 `config.json` / `config.toml` / `venv.json`。

升级时会：

- 保留已有用户值；
- 保留未知的自定义字段和 translator；
- 对普通配置只补充新版本缺失的默认字段；
- 对 `venv.json` 中由项目托管的 package 约束更新为当前版本要求，同时保留用户额外添加的第三方 package；
- 如果旧配置无法解析，会先保存 `.invalid.bak` 后再恢复默认配置。

## 特殊 PDF 解析问题

部分结构异常的 PDF 仍可能在某些 BabelDOC/PyMuPDF 组合中出现：

```text
cannot parse object
Expected dict-like object, got NoneType
```

本版本不会默认重写、重打包或栅格化所有用户 PDF。出现个别异常 PDF 时，建议优先重新下载原文件，必要时只对该文件单独处理。

## Server 源码更新

Server 本身仍通过：

```shell
python server.py --update_source=github
python server.py --update_source=gitee
```

GitHub 更新会使用对应版本的 Release `server.zip`，并在覆盖本地文件前校验下载到的 Server 版本。源码更新与 Python 翻译环境更新仍然是两个独立动作。
