<div align="center">

![Zotero PDF2zh](./favicon@0.5x.svg)

<h2 id="title">Zotero PDF2zh</h2>

[![zotero target version](https://img.shields.io/badge/Zotero-7-green?style=flat-square&logo=zotero&logoColor=CC2936)](https://www.zotero.org)
[![Using Zotero Plugin Template](https://img.shields.io/badge/Using-Zotero%20Plugin%20Template-blue?style=flat-square&logo=github)](https://github.com/windingwind/zotero-plugin-template)
![Downloads release](https://img.shields.io/github/downloads/guaguastandup/zotero-pdf2zh/total?color=yellow)
[![License](https://img.shields.io/github/license/guaguastandup/zotero-pdf2zh)](https://github.com/guaguastandup/zotero-pdf2zh/blob/main/LICENSE)

在Zotero中使用[PDF2zh](https://github.com/Byaidu/PDFMathTranslate)和[PDF2zh_next](https://github.com/PDFMathTranslate/PDFMathTranslate-next)

新版本v3.0.20 | [旧版本v2.4.3](./2.4.3%20version/README.md)

</div>

# 如何使用本插件

本指南将引导您完成 Zotero PDF2zh 插件的安装和配置。

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
mkdir -p zotero-pdf2zh/translated
```

最终文件夹结构应如下：
```
zotero-pdf2zh/
├── docker-compose.yaml
├── Dockerfile
└── zotero-pdf2zh/
    └── translated/
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

参见下方[手动部署指南的第四步到第六步](#第四步-下载并安装插件)，步骤完全一致。

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
    wget https://github.com/guaguastandup/zotero-pdf2zh/releases/download/v3.0.20-beta/server.zip
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

虽然 Zotero 客户端 v3.0.20 版本暂不支持在界面中选择 新挂载的字体，但您可以通过挂载为未来做准备。

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

# 💻 手动部署指南（适合开发者）

如果您熟悉 Python 环境管理，或需要进行深度定制，可以选择手动部署。

❓ 遇到问题

- 阅读[**常见问题文档**](https://docs.qq.com/markdown/DU0RPQU1vaEV6UXJC)
- 尝试向AI提问
- 在github issue区提问
- **将终端报错复制到txt文件，并截图zotero插件设置端配置**，将错误发送到本插件用户QQ群: 971960014，入群验证回答: github
- 访问网络上的视频教程，感谢大家的视频教程！
    - 来自小红薯[@jiajia](https://www.xiaohongshu.com/user/profile/631310d8000000001200c3a1?channelType=web_engagement_notification_page&channelTabId=mentions&xsec_token=AB6wOtAu2rBNcN8WfzJS72pVX6rDZYfWMImRRCx98yX6w%3D&xsec_source=pc_notice)的视频教程: [【zotero PDF文献翻译，免费无需会员，超简单 - jiajia | 小红书 - 你的生活兴趣社区】]( https://www.xiaohongshu.com/discovery/item/68b6cce7000000001c00a555?source=webshare&xhsshare=pc_web&xsec_token=ABI-0NjKTM_1mc2td-UyiWIG4RSUAyxmi2HC8oGmS852I=&xsec_source=pc_share)

## 第零步：安装Python和Zotero
- [Python下载链接](https://www.python.org/downloads/) 建议下载3.12.0版本Python

- 插件目前支持[Zotero 7](https://www.zotero.org/download/)，Zotero 8待适配

## 第一步: 安装uv/conda（可选）

**uv安装(推荐)**

1. 安装uv
```shell
# 方法一: 使用pip安装uv
pip install uv

# 方法二: 下载脚本安装
# macOS/Linux
wget -qO- https://astral.sh/uv/install.sh | sh
# windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

2. 检查uv安装是否成功
```shell
# 显示uv版本号, 则uv安装完成
uv --version
```

**conda安装**

1. 安装conda
参考本链接安装: https://www.anaconda.com/docs/getting-started/miniconda/install#windows-command-prompt

2. 检查conda安装是否成功
```shell
# 显示conda版本号, 则conda安装完成
conda --version
```

## 第二步: 下载项目文件

```shell
# 1. 创建并进入zotero-pdf2zh文件夹
mkdir zotero-pdf2zh && cd zotero-pdf2zh

# 2. 下载并解压server文件夹
# 如果server.zip下载失败, 可以直接访问: https://github.com/guaguastandup/zotero-pdf2zh/releases/download/v3.0.20-beta/server.zip 手动下载
wget https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/server.zip
unzip server.zip

# 3. 进入server文件夹
cd server
```

## 第三步: 准备环境并执行

```shell
# 1. 安装依赖
pip install -r requirements.txt

# 2. 执行脚本
# 默认开启虚拟环境管理
# 默认使用uv进行虚拟环境管理
# 默认自动检查更新
# 默认端口号为8890
# 默认不开启winexe模式
# 默认启用国内镜像进行必要包安装
python server.py


# 可选: 命令行参数:
# 如果要关闭虚拟环境管理
python server.py --enable_venv=False
# 如果要切换虚拟环境管理工具为conda
python server.py --env_tool=conda
# 如果要切换端口号
python server.py --port={Your Port Num}
# 如果要关闭自动检查更新:
python server.py --check_update=False
# 如果要关闭包安装时启用镜像:
python server.py --enable_mirror=Flase

# new feature for Windows user: 开启windows exe安装模式, 安装pdf2zh_next exe版本，将可执行文件路径输入到命令行参数(例如./pdf2zh-v2.4.3-BabelDOC-v0.4.22-win64/pdf2zh/pdf2zh.exe)
python server.py --enable_winexe=True --winexe_path='xxxxxxx'
```

## 第四步: 下载并安装插件

新版本v3.0.20[下载链接](https://github.com/guaguastandup/zotero-pdf2zh/releases/download/v3.0.20-beta/zotero-pdf-2-zh-v3.0.20.xpi)

## 第五步: Zotero端插件设置

<img src="./images/preference.png" alt="preference" style="width: 500px" align="center"/>

**💡 插件设置介绍**

- 免费&免配置的翻译服务:
    - 👍**siliconflowfree**
        - 基于硅基流动提供的GLM4-9B模型, 仅支持翻译引擎pdf2zh_next，由[@硅基流动](https://www.siliconflow.cn/)、[@pdf2zh_next](https://github.com/PDFMathTranslate/PDFMathTranslate-next) 和 [@BabelDOC](https://github.com/funstory-ai/BabelDOC)联合提供服务
    - bing/google
- 免费的翻译服务:
    - **zhipu**(GLM-4.5-Flash模型免费, 需配置API Key)
- 具有优惠/赠送的翻译服务:
    - 加入**火山引擎**共享计划, 可以享受每个模型最高50w赠送额度(翻译配置选择openailiked)
        - 火山引擎的Token赠送量取决于前一天的Token使用量，请注意在火山引擎管理台观察服务赠送Token用量，避免支付超额费用
        - 本服务支持高线程数, 可将线程数设置为500~2000
    - 硅基流动: 通过邀请好友可以获得14元赠送金额
        - 注意，此服务url需填写为: `https://api.siliconflow.cn/v1`

- openailiked可以填写所有兼容openai格式的LLM服务, 您需要填写您的LLM服务供应商提供的URL, API Key, Model名称等信息。
    - 示例: 火山引擎url填写为`https://ark.cn-beijing.volces.com/api/v3`

**💡 注意事项**

- ⚠️⚠️（老用户必看！） 为了避免端口冲突，新版server脚本默认端口号为8890, 旧版本用户需要将Zotero配置页面的Python Server IP修改为: `http://localhost:8890`
- 切换翻译引擎pdf2zh/pdf2zh_next, 界面将显示不同引擎的翻译配置
- 翻译引擎pdf2zh的自定义字体：字体文件路径为本地路径。如果采用远端服务器部署, 暂时无法使用本配置，则需要手动修改`config.json`文件中的`NOTO_FONT_PATH`字段。
- 目前, 额外配置参数名需要与config文件中的字段相同(例如在pdf2zh_next中, openai对应的额外配置: `openai_temperature`和`openai_send_temperature`与`config.toml`文件中的字段相对应), 本功能将在未来继续优化, 可参考[文档](./server/doc/extraData.md)

<img src="./images/editor.png" alt="editor" style="width: 300px" align="center"/>

## 第六步

在Zotero中对条目/PDF右键，选择PDF2zh-翻译选项，进行翻译。

### 关于翻译选项

对条目/附件单击右键, 可以看到四个翻译选项:

<img src="./images/menu.png" alt="menu" style="width: 400px" align="center"/>

**💡 翻译选项解析**

- **翻译PDF**: 点击原文PDF或论文条目, 将会生成在Zotero插件设置端所选择的默认生成文件
- **裁剪PDF**: 选择dual/mono类型附件, 将会对选择的附件在宽度1/2处裁剪, 然后上下拼接, 此功能适合手机阅读
    - 本选项会将页面两侧空白处进行裁剪
    - 若产生截断了原文内容的情况, 可将`server/utils/config.py`中的`config.pdf_w_offset`值降低
- **双语对照**: 点击此选项, 会生成左边为原文, 右边为翻译后文本的PDF
    - 选择"Dual文件翻译页在前"可以交换生成顺序
    - 此选项等同于翻译引擎为pdf2zh_next, 且`双语(Dual)文件显示模式`为**Left&Right**时生成的文件
- **双语对照(裁剪):** 此选项针对双栏PDF论文, 将会在每页生成单栏双语对照内容

示例:

<img src="./images/dualmode.png" alt="dualmode" style="width: 700px" align="center"/>

# FAQ
- Q：我的conda/uv安装失败了，我不想使用虚拟环境管理，怎么办？
- A：如果您只使用pdf2zh_next/pdf2zh引擎中的一个，并且全局python版本为3.12.0，可以不使用虚拟环境管理，执行如下命令即可：
```shell
# 1. 创建并进入zotero-pdf2zh文件夹
mkdir zotero-pdf2zh && cd zotero-pdf2zh

# 2. 下载并解压server文件夹
# 如果server.zip下载失败, 可以直接访问: https://github.com/guaguastandup/zotero-pdf2zh/releases/download/v3.0.20-beta/server.zip 手动下载
wget https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/server.zip
unzip server.zip

# 3. 进入server文件夹
cd server

# 4. 安装执行包
pip install -r requirements.txt

# 5. 执行脚本
# 关闭虚拟环境管理
# 默认自动检查更新
# 默认端口号为8890
# 默认不开启winexe模式
python server.py --enable_venv=False
```

# 致谢

- @Byaidu [PDF2zh](https://github.com/Byaidu/PDFMathTranslate)
- @awwaawwa [PDF2zh_next](https://github.com/PDFMathTranslate/PDFMathTranslate-next)
- @windingwind [zotero-plugin-template](https://github.com/windingwind/zotero-plugin-template)
- [沉浸式翻译](https://immersivetranslate.com)为本项目的活跃贡献者赞助每月Pro会员兑换码，详情请见：[CONTRIBUTOR_REWARD.md](https://github.com/funstory-ai/BabelDOC/blob/main/docs/CONTRIBUTOR_REWARD.md)

# 贡献者

<a href="https://github.com/guaguastandup/zotero-pdf2zh/graphs/contributors"> <img src="https://contrib.rocks/image?repo=guaguastandup/zotero-pdf2zh" /></a>

# 如何支持我

💐 免费开源插件，您的支持是我继续开发的动力～
- ☕️ [Buy me a coffee (Wechat/Alipay)](https://github.com/guaguastandup/guaguastandup) 请在备注中留下您希望出现在赞助者名单的姓名或昵称💗
- 🐳 [爱发电](https://afdian.com/a/guaguastandup)
- 🤖 SiliconFlow邀请链接: https://cloud.siliconflow.cn/i/WLYnNanQ
- [赞助者名单(待更新）](./docs/sponsors.md)
