# 🐳 Docker 部署指南（推荐）

Docker 将服务所需的一切打包，一键启动，无需关心复杂的环境配置，是**最简单、最稳定**的部署方式，强烈推荐新手用户使用。

## 第零步：安装 Docker

在使用 Docker 前，请根据您的操作系统完成 Docker 环境的安装。

<details>
<summary><b>点击展开/折叠 Docker 安装教程</b></summary>

### Windows 用户

1.  **开启 WSL2**：以**管理员身份**打开 PowerShell，执行 `wsl --install`，然后重启电脑。
2.  **安装 Docker Desktop**：访问 [Docker Desktop 官网](https://www.docker.com/products/docker-desktop/) 下载并安装。

### macOS 用户

访问 [Docker Desktop 官网](https://www.docker.com/products/docker-desktop/) 下载并安装。

### Linux 用户

执行以下命令一键安装：
```shell
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER
# 重启或重新登录以生效
```

### 验证安装

打开终端，执行 `docker --version` 和 `docker compose version`，如果能看到版本号，说明安装成功。

</details>

## 第一步：下载部署文件

```shell
# 1. 创建并进入项目文件夹
mkdir zotero-pdf2zh && cd zotero-pdf2zh

# 2. 下载 Docker 配置文件
# 如果 wget 下载失败，可以点击链接手动下载，并放入 zotero-pdf2zh 文件夹
# - docker-compose.yaml: https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/docker/docker-compose.yaml
# - Dockerfile: https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/docker/Dockerfile
wget https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/docker/docker-compose.yaml
wget https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/docker/Dockerfile

# 3. 创建用于存放翻译文件的文件夹
mkdir -p zotero-pdf2zh/config zotero-pdf2zh/translated
```

最终文件夹结构应如下：
```
zotero-pdf2zh/
├── docker-compose.yaml
├── Dockerfile
└── zotero-pdf2zh/
    └── translated/
    ├── config/
    └── LXGWWenKai-Regular.ttf # (可选) 将您的字体文件放在这里
```

## 第二步：启动服务

在确保您位于 `zotero-pdf2zh` 文件夹内后，执行以下命令：

```shell
# 首次启动或需要查看日志时，在前台启动
# 该命令会自动完成镜像构建和容器启动
docker compose up

# 日常使用，在后台静默运行
docker compose up -d
```
服务启动需要一些时间，当您在日志中看到 `* Running on http://0.0.0.0:8890` 时，代表服务已准备就绪。

## 第三步：配置 Zotero 插件

在 Zotero 插件设置中，将 **Python Server IP** 设置为 `http://localhost:8890` 即可开始使用。

## 第四步：容器管理常用命令

| 功能 | 命令 |
| :--- | :--- |
| **查看状态** | `docker compose ps` |
| **查看日志** | `docker compose logs -f` |
| **停止服务** | `docker compose stop` |
| **停止并删除容器** | `docker compose down` |
| **重启服务** | `docker compose restart` |
| **更新服务** | `docker compose pull && docker compose up -d --build` |

## 第五步：插件安装和设置

参见[README.md](https://github.com/guaguastandup/zotero-pdf2zh/blob/main/README.md)(#第四步-下载并安装插件)，步骤完全一致。

---

## 💡 高级用法与常见问题

<details>
<summary><b>Q1: 什么是生产模式和开发模式？如何使用开发模式？</b></summary>

- **生产模式 (默认)**：使用 `docker-compose.yaml` 启动，配置固化在镜像中，稳定高效，适合日常使用。
- **开发模式 (热加载)**：使用 `docker-compose.dev.yaml` 启动，它会将您本地的 `server` 文件夹直接映射到容器中。这意味着您对本地代码和配置的任何修改都会**立即生效**，无需重启容器，适合调试或二次开发。

**如何使用开发模式？**
1.  额外下载 `docker-compose.dev.yaml` 和 `server` 文件夹。
    ```shell
    # 下载 dev 配置文件
    wget https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/docker/docker-compose.dev.yaml
    # 下载并解压 server 文件夹
    wget https://github.com/guaguastandup/zotero-pdf2zh/releases/download/v3.0.25-beta/server.zip
    unzip server.zip
    ```
2.  使用 `-f` 参数指定配置文件启动：
    ```shell
    docker compose -f docker-compose.dev.yaml up -d
    ```
</details>

<details>
<summary><b>Q2: Docker 镜像下载太慢怎么办？</b></summary>

配置国内镜像加速器可大幅提升下载速度。推荐使用 `https://docker.xuanyuan.me`。

**Windows / macOS (Docker Desktop):**
1.  打开 Docker Desktop 设置 -> Docker Engine。
2.  在 JSON 配置中加入以下内容后，点击 "Apply & Restart"。
    ```json
    {
      "registry-mirrors": ["https://docker.xuanyuan.me"]
    }
    ```

**Linux:**
执行以下命令自动配置并重启 Docker。
```shell
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json <<-'EOF'
{
  "registry-mirrors": ["https://docker.xuanyuan.me"]
}
EOF
sudo systemctl daemon-reload
sudo systemctl restart docker
```
</details>

<details>
<summary><b>Q3: 如何使用自定义字体？</b></summary>

虽然 Zotero 客户端 v3.0.25 版本暂不支持在界面中选择 新挂载的字体，但您可以通过挂载为未来做准备。

1.  将您的字体文件（如 `LXGWWenKai-Regular.ttf`）放入 `zotero-pdf2zh/zotero-pdf2zh/` 文件夹。
2.  修改 `docker-compose.yaml`，取消字体挂载的注释：
    ```yaml
    # ...
    volumes:
      - ./zotero-pdf2zh/translated:/app/server/translated
      # 取消下面一行的注释
      - ./zotero-pdf2zh/LXGWWenKai-Regular.ttf:/app/LXGWWenKai-Regular.ttf
    ```
3.  重启容器：`docker compose up -d --build`。
</details>

<details>
<summary><b>Q4: 端口 8890 被占用了怎么办？</b></summary>

修改 `docker-compose.yaml` 中的端口映射，将冒号前的端口改成其他未被占用的端口，如 `8891`。
```yaml
ports:
  - "8891:8890" # 本地端口:容器端口
```
同时，在 Zotero 插件中将服务地址改为 `http://localhost:8891`。
</details>

<details>
<summary><b>Q5: 什么是 `restart: unless-stopped`？</b></summary>

这是 Docker 的一项重启策略，能确保服务的稳定性。它意味着：
- **除非您手动执行 `docker compose stop` 命令**，否则容器在任何情况下（如服务器重启、程序崩溃）都会自动重新启动。
- 这让您无需担心服务意外中断，是后台服务的最佳实践。
</details>

<details>
<summary><b>Q6: 新版 Docker 部署和旧版插件(v2.4.3)的部署有什么区别？</b></summary>

新版 Docker 部署进行了全面优化，更简单、更强大。主要区别如下：

- **引擎变更**：新版 Docker **仅支持 `pdf2zh_next` 引擎**，暂不兼容旧的 `pdf2zh` 引擎。这是因为新版直接基于预装了 `next` 引擎的镜像构建，性能更优。
- **部署简化**：无需再手动创建 `config.json`。您只需下载 `docker-compose.yaml` 和 `Dockerfile` 两个文件，即可一键启动。
- **自动打包**：新版 Docker 会自动下载完整的 `server.zip` 服务包，而不是像旧版一样只依赖单个 `server.py` 文件，服务更完整、更稳定。

总之，如果您是老用户，请注意新版 Docker 暂不支持旧的 `pdf2zh` 引擎，其他方面体验将全面优于旧版。
</details>

---
