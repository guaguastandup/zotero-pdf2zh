# 翻译环境安装与更新

Zotero PDF2zh 从 **v4.1.0** 起将 **Server/插件源码更新** 与 **Python 翻译环境更新** 分开处理。当前版本在已有 conda/uv 环境里**直接安装依赖**，不再创建 staging 或 backup 环境。

::: tip 当前更新方式
- 已有环境：在 `zotero-pdf2zh-next-venv` 里直接 `pip` / `uv pip` 安装。
- Windows Conda 会先查 `<env>\\python.exe`，找不到时再用 `conda run -n ... python` 询问真实路径。
- 以前残留的 `*-staging` / `*-backup` 环境会在更新时清理，翻译只使用正式环境。
- 托管环境不会继承系统 `PYTHONPATH` / `PYTHONHOME`；代理、CUDA 和 PATH 等其他设置保持不变。
- 如果发现 `pydantic_core` 等关键二进制依赖损坏或来自全局 Python，会重新安装完整依赖，而不是继续使用混合环境。
:::

## 新用户

新用户无需手工安装 BabelDOC、PyMuPDF 或指定 `pdf2zh_next` 的具体版本。

第一次真正使用 `pdf2zh_next` 时，Server 会：

1. 沿用已有 uv/conda，没有则创建正式环境（新用户优先 uv）；
2. 检测 PyPI、USTC、TUNA、阿里云等下载源；
3. 在当前环境中安装 `pdf2zh_next==2.10.2`、`BabelDOC==0.7.1`、`PyMuPDF==1.28.2` 及其依赖；
4. 检查依赖完整性和 CLI 入口；
5. 对 `pdf2zh_next` 额外确认 DeepSeek V4 thinking 参数可用。

这三项关键依赖固定为本轮测试基线。未来升级由后续 Zotero PDF2zh 版本验证后调整，其他传递依赖仍按上游声明解析。

Server 本身仍然可以启动。如果安装失败，可稍后运行 `python update_packages.py` 重试。

## 已有用户更新

如果 Server 检测到已有 `pdf2zh_next` 环境与基线不匹配，交互式启动时会询问；每个 Server 版本与依赖基线组合只提示一次：

```text
🔄 检测到已有 Python 翻译环境
当前 pdf2zh_next: ...

[Y] 检查并更新（推荐）
[N] 暂不更新

选择 [Y/n]:
```

直接回车等同于选择 `Y`。更新会在当前环境中直接安装依赖，已有更高版本也可能调整回基线。只有 `pdf2zh_next`、BabelDOC、PyMuPDF 三项均匹配时才因版本匹配跳过提示。非交互式启动和 Windows 独立 exe 不显示此提示。

如果选择 `N`，同一 Server 版本与依赖基线组合不会反复询问；之后仍可随时手工更新：

```shell
python update_packages.py
```

## 普通用户只需这一条命令

进入 `server` 目录：

```shell
python update_packages.py
```

它会自动沿用已有 uv/conda 环境；没有已有环境时优先使用 uv。BabelDOC 版本由随 Server 提供的配置统一指定，无需用户单独选择。

这个命令只维护翻译环境。Server 的 crop-compare 使用启动 Server 的 Python 环境中的 PyMuPDF；请在该环境中运行 `python -m pip install -r requirements.txt`，或使用 `uv run --python 3.12 --with-requirements requirements.txt server.py` 启动。旧引擎 `pdf2zh==1.9.11` 的独立环境保留 `PyMuPDF<1.25.3` 约束。

流程：

```text
找到或创建正式环境
    ↓
网络与依赖检查
    ↓
在当前环境安装
    ↓
验证 CLI / 关键二进制依赖
```

如果已有环境已经损坏，普通用户仍然只需运行这条命令。工具会先隔离全局 Python 路径；检测到关键依赖不可导入时，会自动执行一次完整重装。健康环境不会因此重复安装。

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

### 更新

```shell
python manage_packages.py update
```

与 `python update_packages.py` 相同，都是在当前环境中直接安装。

## “最新版”的含义

更新工具不会使用 `--no-deps` 绕过上游依赖约束。

因此这里的“更新”准确含义是：

> **安装当前 Zotero PDF2zh 提供的固定测试组合，并遵循上游依赖约束。**

当前基线为 `pdf2zh_next 2.10.2 + BabelDOC 0.7.1 + PyMuPDF 1.28.2`。BabelDOC 0.7.1 要求 `PyMuPDF>=1.26.7,<2`，因此不会单独将 PyMuPDF 升至 2.x。这不是完整的依赖锁文件；其他传递依赖仍由包管理器解析。

## DeepSeek V4 Thinking

DeepSeek V4 显式 Thinking 控制要求实际执行的 `pdf2zh_next` 支持：

```text
--deepseek-thinking-mode
--deepseek-reasoning-effort
```

新安装使用 `pdf2zh_next==2.10.2`，DeepSeek 思考控制的最低版本判断仍为 2.9.0。安装后还会通过已安装 distribution 的静态 metadata/source 检查 runtime capability；不会为了检查能力启动 `pdf2zh_next --help`。

如果已有用户拒绝更新，仍然可以继续使用旧环境支持的其他功能。DeepSeek V4 新配置默认关闭思考，已保存的开关会被保留。开启与关闭都需要支持思考控制的运行时（`pdf2zh_next >= 2.9.0`）；不支持时会在 API 调用前提示更新，因为省略控制参数会采用服务端默认的开启行为。

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

GitHub 与 Gitee 都会用来检查版本和下载 `server.zip`。`--update_source` 只决定**优先尝试哪一个**；失败或该源版本更旧时，会自动改用另一个源。下载后仍会校验 zip 和 Server 版本。

Gitee Release 附件可能弹出安全验证或返回 404，因此还会尝试 Gitee `raw/vX.Y.Z/server.zip`、GitHub Release，以及仓库里的 `raw.githubusercontent.com/.../vX.Y.Z/server.zip`。不要使用 Gitee 源码归档（`repository/archive/*.zip`），该地址经常返回 HTML 页面。

手动下载：

```text
https://github.com/guaguastandup/zotero-pdf2zh/releases/latest/download/server.zip
https://gitee.com/guaguastandup/zotero-pdf2zh/raw/v4.1.1/server.zip
```

源码更新与 Python 翻译环境更新仍然是两个独立动作。

## 项目通知

Server 启动时会从仓库 `main` 上的 `server/notice.json` 拉取内容。`community`（QQ 群、文档链接）每次启动都会显示；`notices` 按本机版本过滤。获取失败会跳过，不影响启动。

改 QQ 群号、下线旧公告、或提醒某个版本无法自动更新时，只要改这份文件并推到 `main`，不必再发一个 Server 版本。

```json
{
  "community": {
    "qq_groups": [{ "name": "8群", "id": "1093571926", "status": "open" }]
  },
  "notices": [
    {
      "id": "410-manual-update",
      "enabled": true,
      "level": "warn",
      "affects": ["4.1.0"],
      "title": "4.1.0 无法自动更新到 4.1.2",
      "message": "请手动下载 server.zip，解压后覆盖本地 server 目录。"
    }
  ]
}
```

`affects` 为空或含 `*` 时对所有版本显示；也可用 `min_version` / `max_version`。`enabled` 设为 `false` 即可下线。`qq_groups` 里 `status` 为 `full` 的群不会打印。
