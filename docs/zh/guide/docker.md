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
