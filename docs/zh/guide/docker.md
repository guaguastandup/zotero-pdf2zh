# Docker 部署

使用 Docker 部署可以避免本地环境配置问题，实现更好的环境隔离。

::: tip Docker 优势
- 环境隔离，不影响本地 Python 环境
- 部署快速，一次配置永久使用
- 易于迁移和备份
:::

---

## 前置要求

确保已安装 Docker：

```bash
docker version
docker compose version
```

> 如果显示不了 `docker compose`，可能安装的是老版 `docker-compose`，后续命令把 `docker compose` 换成 `docker-compose` 即可。

---

## 快速开始

### 1. 下载并解压 docker.zip

**Windows (CMD):**

```cmd
mkdir zotero-pdf2zh_docker
cd zotero-pdf2zh_docker

curl -L -o docker.zip https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/docker.zip
powershell -Command "Expand-Archive -Path '.\docker.zip' -DestinationPath '.' -Force"
cd docker
```

**macOS / Linux:**

```bash
mkdir -p zotero-pdf2zh_docker
cd zotero-pdf2zh_docker

curl -L -o docker.zip https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/docker.zip
unzip -o docker.zip -d .
cd docker
```

### 2. 预拉取镜像

```bash
docker pull awwaawwa/pdfmathtranslate-next:latest
```

### 3. 启动服务

```bash
docker compose up -d --build
```

看到类似输出即表示启动成功：

```
* Running on http://127.0.0.1:8890
* Running on http://172.18.0.2:8890
```

### 常用命令

```bash
docker start zotero-pdf2zh    # 启动
docker stop zotero-pdf2zh     # 停止
docker logs -f zotero-pdf2zh  # 查看实时日志
```

---

## 切换为 pdf2zh 引擎

默认使用 pdf2zh_next，如需切换为 pdf2zh：

### 1. 预拉取镜像

```bash
docker pull byaidu/pdf2zh:1.9.6
```

### 2. 修改 Dockerfile

找到：

```dockerfile
ZOTERO_PDF2ZH_FROM_IMAGE=awwaawwa/pdfmathtranslate-next:latest
```

改为：

```dockerfile
ZOTERO_PDF2ZH_FROM_IMAGE=byaidu/pdf2zh:1.9.6
```

### 3. 修改 docker-compose.yaml

找到：

```yaml
ZOTERO_PDF2ZH_FROM_IMAGE: awwaawwa/pdfmathtranslate-next:latest
```

改为：

```yaml
ZOTERO_PDF2ZH_FROM_IMAGE: byaidu/pdf2zh:1.9.6
```

### 4. 重构启动

```bash
docker compose down
docker compose up -d --build
```

---

## 镜像加速

### 方法一：代理前缀

编辑 `docker-compose.yml`，在 `build.args` 下添加：

```yaml
GITHUB_PROXY_PREFIX: "https://ghproxy.net/"
```

### 方法二：jsDelivr CDN

编辑 `docker-compose.yml`：

```yaml
SERVER_ZIP_URL: "https://cdn.jsdelivr.net/gh/guaguastandup/zotero-pdf2zh@main/server.zip"
```

重新构建：

```bash
docker compose build --no-cache
docker compose up -d
```

---

## 其他部署方式

- **Docker Hub 镜像**: [vanxv/zotero-pdf2zh](https://hub.docker.com/r/vanxv/zotero-pdf2zh)
- **Homebrew 部署** (macOS/Linux): [NightWatcher314/zotero-pdf2zh-server](https://github.com/NightWatcher314/zotero-pdf2zh-server)

---

## 下一步

- [配置说明](/zh/guide/configuration) - 插件和服务配置
- [常见问题](/zh/guide/faq/) - 遇到问题？

## 主动更新（无需在容器中输入 y/n）

在**宿主机**的 `docker` 目录执行，先等待正在进行的翻译完成。

macOS / Linux：

```sh
sh update.sh          # 默认只更新 Server 镜像
sh update.sh all      # 同时拉取 Compose 配置指定的翻译引擎镜像
```

Windows PowerShell：

```powershell
.\update.ps1
.\update.ps1 all
```

脚本先检查 Compose 配置，再无缓存构建并拉取基础镜像，成功后重建
`pdf2zh-server` 服务。不执行 `down -v` 或清理卷；已有 `config` 和 `translated`
挂载保留。构建或引擎拉取失败时不重启现有服务。重建阶段会短暂中断服务，
不是零停机更新。最后检查 `docker compose logs --tail=50 pdf2zh-server` 确认启动成功。

更新使用 Compose 中原有的下载地址、代理和镜像配置。若固定到某个旧版本，
重复更新仍会得到该版本，需要先修改配置。开发分支代码尚未发布为 `server.zip` 时，
此命令不会自动部署这些源码；仍以构建时下载的包为准。
旧版 docker.zip 不含这些脚本，需先取得更新后的部署脚本。

Docker 内不要运行 `python update_packages.py` 来替代镜像更新：该工具管理
uv/Conda 环境，不负责重建 Docker 镜像。运行容器内直接改包也会在重建后丢失。

### charset / Requests 版本诊断

需要区分 `charset-normalizer` 与 `chardet`。2026-11-25 核对，前者最新为
3.5.3，仍满足 Requests 的 `>=2,<4`；后者为 7.7.0，可能超出旧 Requests 的
`>=3.0.2,<6` 检查范围。不能仅凭警告里同时出现 charset 就判断前者过高。

用**实际报错的引擎 Python**执行 `python /path/to/server/check_charset.py`，
会列出版本并捕获 Requests 导入警告，不修改依赖。Docker 的 Server 和子引擎是
不同容器，应在报错对应的镜像中检查。也可以查看镜像的包列表：

```sh
docker compose exec -T pdf2zh-server python /app/server/check_charset.py
# 子引擎请将镜像名换成实际配置值；诊断脚本需使用包含该脚本的新 Server 包。
docker run --rm --entrypoint python awwaawwa/pdfmathtranslate-next:latest -m pip show requests charset-normalizer chardet
```

若镜像没有 pip，可用 Python 的 `importlib.metadata.version()` 查询。
确认包名、Requests 版本及警告全文后再选择兼容组合，不盲目升级或降级。
