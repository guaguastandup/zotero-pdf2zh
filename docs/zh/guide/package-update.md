# 包更新

Zotero PDF2zh 将 **Server/插件源码更新** 与 **Python 翻译环境更新** 分开处理。

## 默认策略：不自动升级翻译环境

正常执行：

```shell
python server.py
```

不会为了追随最新版而主动升级现有 `pdf2zh` / `pdf2zh_next` 环境。只要当前环境已经满足 Server 声明的基本依赖，Server 会继续使用它。

这样做是为了避免上游 `pdf2zh_next`、BabelDOC、PyMuPDF 等组件升级后改变 PDF parser、排版或依赖关系，从而让原本可用的环境突然出现兼容性回归。

> `server.py --check_update=True` 检查的是 **Zotero PDF2zh Server 源码版本**，不是 Python 翻译包版本。两者不要混淆。

## 查看当前翻译环境版本

进入 `server` 目录：

```shell
python manage_packages.py status
```

默认检查 `pdf2zh_next`，会显示类似：

```text
pdf2zh-next    2.9.0
BabelDOC       0.6.2
PyMuPDF        1.25.2
pypdf          6.16.1
```

检查其他环境：

```shell
python manage_packages.py status --engine pdf2zh
python manage_packages.py status --engine all
```

该命令是只读的，不会安装、删除或升级任何包。

## 显式更新到最新兼容版本

只有在您明确希望升级时才执行：

```shell
python manage_packages.py update
```

默认只更新 `pdf2zh_next` 环境。更新前会显示当前版本和计划更新的包，并要求再次确认。

也可以更新全部翻译环境：

```shell
python manage_packages.py update --engine all
```

脚本使用包管理器的正常依赖解析，不会使用 `--no-deps` 绕过上游约束。因此这里的“最新版”准确地说是：

> **当前上游依赖声明允许安装的最新兼容组合。**

这比强制把每个组件单独升级到绝对最新版更安全。

如果需要脚本化执行，可以使用：

```shell
python manage_packages.py update --yes
```

如果需要指定镜像源：

```shell
python manage_packages.py update \
  --index-url "https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/"
```

## DeepSeek V4 思考控制

`deepseek_thinking_mode` / `deepseek_reasoning_effort` 需要 `pdf2zh_next >= 2.9.0`。

如果您需要 DeepSeek V4 的显式思考开关，可以先执行：

```shell
python manage_packages.py status
```

版本不足时，再由用户主动决定是否执行：

```shell
python manage_packages.py update
```

Server 不会为了启用该功能而在后台静默升级整个翻译环境。

## 关于 pdf2zh_next 2.9.0 / BabelDOC 0.6.x

`pdf2zh_next 2.9.0` 引入了 BabelDOC 0.6 系列的新 PDF parser。部分结构不规范、xref/indirect object 有异常但普通阅读器仍能打开的 PDF，可能在新 parser 中暴露解析错误。

`manage_packages.py status` 会针对已知的 `pdf2zh-next >= 2.9.0 + BabelDOC <= 0.6.2` 组合显示提示。

不要为了追求某个单独组件的最新版而使用 `--no-deps` 强行覆盖依赖。上游 release bundle 与 Python 包元数据可能在短期内不同步，应优先采用上游声明为兼容的组合。

如果只有个别 PDF 出现 `cannot parse object` / `Expected dict-like object, got NoneType`，建议先重新下载原始 PDF，或将该文件单独重打包后再翻译，而不是让 Zotero PDF2zh 默认重写所有用户 PDF。

## 回到“完全不更新”

不需要执行任何命令。继续正常运行：

```shell
python server.py
```

即可保留当前翻译环境。

## Server 源码更新源

Server 自身的更新源仍可通过：

```shell
python server.py --update_source=github
python server.py --update_source=gitee
```

控制。这与 `manage_packages.py` 的 Python 包维护是两套独立机制。
