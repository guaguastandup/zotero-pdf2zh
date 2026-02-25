# Package Update

This document describes how to update Zotero PDF2zh dependencies.

## Update Methods

### Manual Update

```shell
cd server
pip install -r requirements.txt --upgrade
```

### Automatic Update

Both plugin and server script support automatic update functionality.

Start `server.py` will automatically check for updates (`--check_update=True`, enabled by default).

## Update Source Configuration

Specify update source via command line parameters:

```shell
# Use GitHub
python server.py --update_source=github

# Use Gitee (recommended in China)
python server.py --update_source=gitee
```

## Mirror Source Configuration

If download speed is slow, configure domestic mirror sources:

```shell
# Use Tsinghua mirror
python server.py --mirror_source="https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple/"

# Disable mirror
python server.py --enable_mirror=False
```
