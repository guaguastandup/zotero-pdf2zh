# 安装指南

本文档适用于 Zotero PDF2zh **v4.1.0**。v4.1.0 之后，Server 源码、Zotero 插件和 Python 翻译环境分别维护：普通用户不需要手工决定 `pdf2zh_next`、BabelDOC、PyMuPDF 的具体版本。

::: tip 开始之前
建议准备：
- **Python 3.12**（推荐）
- **Zotero 7 或 Zotero 8**
- **uv**（推荐的新用户环境管理器）或已有的 conda
:::

## 1. 下载 Server

请从 GitHub Release 下载 `server.zip`，不要再使用仓库 `main` 分支中的静态 zip：

```text
https://github.com/guaguastandup/zotero-pdf2zh/releases/latest/download/server.zip
```

下载后解压，目录结构应为：

```text
zotero-pdf2zh/
└── server/
    ├── server.py
    ├── requirements.txt
    ├── update_packages.py
    ├── config/
    └── utils/
```

进入 `server` 目录：

```shell
cd server
```

## 2. 安装 Server 自身依赖

这一步只安装 Flask、TOML、PDF 基础库等 **Server 运行依赖**，不会要求您手工安装 `pdf2zh_next` / BabelDOC：

```shell
python -m pip install -r requirements.txt
```

## 3. 推荐：安装 uv

如果电脑里还没有本项目的翻译环境，推荐安装 uv：

```shell
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

验证：

```shell
uv --version
```

已有 conda 用户不需要迁移到 uv。v4.1.0 的默认 `env_tool=auto` 会优先沿用已经存在的 uv / conda 项目环境；只有没有旧环境时才优先新建 uv 环境。

## 4. 启动 Server

普通用户直接运行：

```shell
python server.py
```

默认地址：

```text
http://127.0.0.1:8890
```

Server 默认只监听 `127.0.0.1`。只有确定需要让其他设备访问时，才显式使用：

```shell
python server.py --host 0.0.0.0
```

::: warning 远程访问
使用 `--host 0.0.0.0` 会把服务暴露给当前网络中的其他设备。只有在您理解网络/防火墙设置时才这样做。
:::

## 5. 新用户第一次翻译时会发生什么？

新用户不需要预先执行 `pip install pdf2zh_next`。

第一次真正使用 `pdf2zh_next` 时，Server 会自动：

1. 选择环境管理器（无旧环境时优先 uv）；
2. 测试 PyPI / USTC / TUNA / 阿里云等下载源；
3. 创建独立 staging 环境；
4. 安装 v4.1.0 支持范围内最新兼容的 `pdf2zh_next`（`>=2.9.0,<3.0.0`）及其依赖；
5. 验证依赖和 DeepSeek V4 capability；
6. 全部成功后才切换为正式环境。

安装失败不会留下一个被当成正常环境使用的“半安装” venv。

## 6. 老用户升级到 v4.1.0

已有 uv / conda 翻译环境的用户启动新版 Server 时，会询问一次是否安全更新：

```text
🔄 检测到已有 Python 翻译环境
当前 pdf2zh_next: ...

[Y] 安全检查并更新（推荐）
[N] 暂不更新

选择 [Y/n]:
```

建议直接回车选择 `Y`。

更新采用：

```text
staging 安装
→ 验证
→ 成功后切换
→ 失败继续使用旧环境
```

不会在当前可用环境中直接执行原地 upgrade。选择 `N` 后，旧环境仍可继续使用它原本支持的功能；如果以后使用必须依赖新版 runtime 的 DeepSeek V4 Thinking Control，Server 会在 API 请求前安全阻止并提示更新。

如果以后想主动重试更新：

```shell
python update_packages.py
```

该命令会自动识别已有 uv / conda；没有已有环境时优先 uv。

## 7. conda 用户

如果您以前已经使用 conda，正常运行：

```shell
python server.py
```

即可让 `auto` 模式发现并沿用已有 conda 环境。

如果希望强制只使用 conda：

```shell
python server.py --env_tool=conda
python update_packages.py --env-tool conda
```

显式选择 conda 后，失败不会自动切换成 uv；显式选择 uv 同理。

## 8. 不使用托管虚拟环境（高级）

只有明确知道自己在维护哪个 Python 环境时才建议：

```shell
python server.py --enable_venv=False
```

此模式下 Server 不负责升级您的系统 Python 环境。DeepSeek V4 等功能仍会检查实际 runtime capability。

## 9. 安装 Zotero 插件

最新 XPI：

```text
https://github.com/guaguastandup/zotero-pdf2zh/releases/latest/download/zotero-pdf-2-zh.xpi
```

安装步骤：

1. Zotero →「工具」→「插件」；
2. 将下载的 `.xpi` 拖入插件窗口；
3. 安装后重启 Zotero；
4. 打开「工具 → PDF2zh 首选项」；
5. Python Server IP 保持 `http://127.0.0.1:8890`（除非您自己修改过地址）。

## 10. v4.1.0 默认启动参数

| 参数 | 默认值 | 说明 |
|---|---|---|
| `--host` | `127.0.0.1` | 默认只允许本机访问 |
| `--port` | `8890` | Server 端口 |
| `--enable_venv` | `True` | 启用托管翻译环境 |
| `--env_tool` | `auto` | 沿用已有 uv/conda；新环境优先 uv |
| `--check_update` | `True` | 启动时检查 Server 更新 |
| `--update_source` | `gitee` | Server 更新检查源，可改为 github |
| `--enable_mirror` | `True` | 启用 Python 包下载源优化 |
| `--skip_install` | `False` | 是否禁止自动创建/修复翻译环境 |

常见示例：

```shell
# 更换端口
python server.py --port 9999

# 强制使用 uv
python server.py --env_tool=uv

# 强制使用 conda
python server.py --env_tool=conda

# 使用 GitHub Release 检查 Server 更新
python server.py --update_source=github

# 允许局域网访问（高级）
python server.py --host 0.0.0.0
```

## 11. Windows standalone exe（高级）

Windows 用户也可以使用 `pdf2zh_next` 上游提供的 standalone exe，并通过：

```shell
python server.py --enable_winexe=True --winexe_path="<pdf2zh.exe 路径>"
```

standalone exe 的版本需要自行维护。DeepSeek V4 Thinking Control 会在调用前检查该 exe 是否支持对应能力；不支持时不会静默忽略设置。

## 注意事项

- 翻译期间需要保持 `server.py` 运行。
- 不要手工使用 `--no-deps` 强装 BabelDOC / PyMuPDF / pdf2zh_next。
- 新版翻译环境更新请优先使用 Server 启动提示或 `python update_packages.py`。
- 个别结构异常 PDF 仍可能触发上游 BabelDOC / PyMuPDF 解析问题；本项目不会默认重写或栅格化所有用户 PDF。

## 下一步

- [配置说明](/zh/guide/configuration)
- [翻译选项](/zh/guide/translation-options)
- [额外参数](/zh/guide/extra-params)
- [翻译环境更新](/zh/guide/package-update)
- [常见问题](/zh/guide/faq/)
