# 包更新

本文档介绍如何更新 Zotero PDF2zh 的依赖包。

## 更新方式

### 手动更新

```shell
# 进入 server 目录
cd server

# 更新依赖包
pip install -r requirements.txt --upgrade

# 或使用 uv
uv pip install -r requirements.txt --upgrade
```

### 自动更新

插件和 Server 脚本均支持自动更新功能。

启动 `server.py` 时会自动检查更新（`--check_update=True`，默认开启）。

## 更新源配置

您可以通过命令行参数指定更新源：

```shell
# 使用 GitHub 更新源
python server.py --update_source=github

# 使用 Gitee 更新源（国内推荐）
python server.py --update_source=gitee
```

## 镜像源配置

如果下载速度较慢，可以配置国内镜像源：

```shell
# 使用清华镜像
python server.py --mirror_source="https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/"

# 关闭镜像
python server.py --enable_mirror=False
```

## 常见问题

### 更新失败

1. 检查网络连接
2. 尝试切换更新源或镜像源
3. 手动下载并安装依赖包

### 版本兼容问题

如果更新后出现兼容性问题，可以重新安装特定版本：

```shell
pip install -r requirements.txt --force-reinstall
```
