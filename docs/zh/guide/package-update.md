# 包更新

Zotero PDF2zh 将 **Server/插件源码更新** 与 **Python 翻译环境更新** 分开处理。

## 普通用户：只需要这一条命令

进入 `server` 目录后执行：

```shell
python update_packages.py
```

就可以完成 Python 翻译环境的安全更新。用户不需要自己判断 PyPI、镜像、BabelDOC、PyMuPDF 或依赖版本。

这个命令内部会自动：

1. 找到当前 `pdf2zh_next` 虚拟环境；
2. 检测 PyPI、USTC、TUNA、阿里云等下载源；
3. 检查真正的包文件是否能下载；
4. 自动选择可用且速度较好的源；
5. 先做依赖解析预检，不修改现有环境；
6. 仅安装当前依赖约束允许的兼容版本；
7. 首选源失败时自动切换到已经验证过的备用源；
8. 如果没有安全可用的更新路径，则停止更新并保留当前环境。

执行 `update_packages.py` 本身就代表用户主动选择更新，因此不会再额外询问一次 `y/N`。

::: tip 默认不会自动更新
正常启动：

```shell
python server.py
```

不会主动升级现有 `pdf2zh` / `pdf2zh_next` 环境。只有用户显式执行 `python update_packages.py` 时才会更新 Python 翻译包。
:::

## 高级诊断

普通用户不需要使用下面的命令。排查问题时可以使用 `manage_packages.py`。

### 检查下载网络

```shell
python manage_packages.py network
```

该命令只检测网络，不修改环境。它会测试：

- PyPI 官方源
- USTC PyPI 镜像
- TUNA PyPI 镜像
- 阿里云 PyPI 镜像

检测不只访问镜像首页，还会针对 `pdf2zh-next` 的包索引读取一个 distribution 文件的小片段，用于判断真正的包下载链路是否可用。

如果全部失败，并且系统存在 `HTTP_PROXY` / `HTTPS_PROXY` / `ALL_PROXY`，诊断会提示代理配置可能已经失效，但不会打印代理密码或 token。

### 查看当前版本

```shell
python manage_packages.py status
```

输出类似：

```text
pdf2zh-next    2.9.0
BabelDOC       0.6.2
PyMuPDF        1.25.2
pypdf          6.16.1
```

### 自定义镜像或超时

```shell
python update_packages.py \
  --index-url "https://pypi.tuna.tsinghua.edu.cn/simple"

python update_packages.py --network-timeout 8
```

## 更新原则

更新脚本使用 uv/pip 的正常依赖解析，不使用 `--no-deps` 绕过上游约束。因此“更新到最新版”准确地说是：

> **更新到当前上游依赖声明允许的最新兼容组合。**

如果某个单独组件存在更新，但与当前 `pdf2zh_next` 依赖约束冲突，脚本不会强制安装不兼容组合。

## DeepSeek V4 思考控制

`deepseek_thinking_mode` / `deepseek_reasoning_effort` 需要 `pdf2zh_next >= 2.9.0`。需要更新时，普通用户仍然只运行：

```shell
python update_packages.py
```

Server 不会为了启用该功能在后台静默升级环境。

## 关于特殊 PDF 解析问题

部分结构不规范、xref/indirect object 有异常但普通阅读器仍能打开的 PDF，可能在某些 BabelDOC parser 版本中出现解析错误。

如果只有个别 PDF 出现 `cannot parse object` / `Expected dict-like object, got NoneType`，建议先重新下载原始 PDF，或仅对该文件进行重打包，而不是让 Zotero PDF2zh 默认重写所有用户 PDF。

## 完全不更新

什么都不用做。继续正常运行：

```shell
python server.py
```

即可保留当前翻译环境。

## Server 源码更新

Server 自身的更新仍通过：

```shell
python server.py --update_source=github
python server.py --update_source=gitee
```

控制。这与 `update_packages.py` 的 Python 包更新是两套独立机制。
