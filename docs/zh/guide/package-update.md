# 翻译环境安装与更新

Zotero PDF2zh 从 **v4.1.0** 起将 **Server/插件源码更新** 与 **Python 翻译环境更新** 分开处理。当前版本在已有 conda/uv 环境里**直接安装依赖**，不再创建 staging 或 backup 环境。

::: tip 当前更新方式
- 已有环境：在 `zotero-pdf2zh-next-venv` 里直接 `pip` / `uv pip` 安装。
- Windows Conda 会先查 `<env>\\python.exe`，找不到时再用 `conda run -n ... python` 询问真实路径。
- 以前残留的 `*-staging` / `*-backup` 环境会在更新时清理，翻译只使用正式环境。
:::

## 新用户

新用户无需手工安装 BabelDOC、PyMuPDF 或指定 `pdf2zh_next` 的具体版本。

第一次真正使用 `pdf2zh_next` 时，Server 会：

1. 沿用已有 uv/conda，没有则创建正式环境（新用户优先 uv）；
2. 检测 PyPI、USTC、TUNA、阿里云等下载源；
3. 在当前环境中安装 `pdf2zh_next >= 2.9.0,<3.0.0` 及其依赖；
4. 检查依赖完整性和 CLI 入口；
5. 对 `pdf2zh_next` 额外确认 DeepSeek V4 thinking 参数可用。

这里故意限制在 `pdf2zh_next 2.x`。未来如果上游发布 3.x，需要由后续 Zotero PDF2zh 版本验证并放开支持范围。

Server 本身仍然可以启动。如果安装失败，可稍后运行 `python update_packages.py` 重试。

## 已有用户更新

如果 Server 检测到已经存在 `pdf2zh_next` 环境，首次启动当前 Server 版本时会询问：

```text
🔄 检测到已有 Python 翻译环境
当前 pdf2zh_next: ...

[Y] 检查并更新（推荐）
[N] 暂不更新

选择 [Y/n]:
```

直接回车等同于选择 `Y`。更新会在当前环境中直接安装依赖。如果当前 `pdf2zh_next` 已经是 **2.9.0 或更高**，启动时不会再询问这次更新。

如果选择 `N`，当前 Server 版本不会反复询问；之后仍可随时手工更新：

```shell
python update_packages.py
```

## 普通用户只需这一条命令

进入 `server` 目录：

```shell
python update_packages.py
```

它会自动沿用已有 uv/conda 环境；没有已有环境时优先使用 uv。BabelDOC 是 `pdf2zh_next` 的依赖，不需要单独指定版本。

流程：

```text
找到或创建正式环境
    ↓
网络与依赖检查
    ↓
在当前环境安装
    ↓
验证 CLI / 依赖
```

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

> **安装当前 Zotero PDF2zh 支持范围和上游依赖声明共同允许的最新兼容组合。**

对于 v4.1.0，`pdf2zh_next` 的托管范围是 `>=2.9.0,<3.0.0`。同时，不保证 BabelDOC、PyMuPDF 等每一个独立组件都达到各自的绝对最新版本。如果上游依赖元数据不允许某个组合，Zotero PDF2zh 不会强制安装它。

## DeepSeek V4 Thinking

DeepSeek V4 显式 Thinking 控制要求实际执行的 `pdf2zh_next` 支持：

```text
--deepseek-thinking-mode
--deepseek-reasoning-effort
```

v4.1.0 的新安装要求 `pdf2zh_next >= 2.9.0,<3.0.0`，并且安装后还会通过已安装 distribution 的静态 metadata/source 检查 runtime capability；不会为了检查能力启动 `pdf2zh_next --help`。

如果已有用户拒绝更新，仍然可以继续使用旧环境已有功能。DeepSeek V4 **默认不思考**：旧 runtime 会放行翻译。只有用户在插件里手动开启思考时，才要求 `pdf2zh_next >= 2.9.0`；旧环境无法执行思考时会在 API 调用前拦截，避免设置被忽略还扣费。

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
