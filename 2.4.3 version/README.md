# Zotero PDF2zh

<div align="center">

![Zotero PDF2zh](../favicon@0.5x.svg)

[![zotero target version](https://img.shields.io/badge/Zotero-7-green?style=flat-square&logo=zotero&logoColor=CC2936)](https://www.zotero.org)
[![Using Zotero Plugin Template](https://img.shields.io/badge/Using-Zotero%20Plugin%20Template-blue?style=flat-square&logo=github)](https://github.com/windingwind/zotero-plugin-template)
![Downloads release](https://img.shields.io/github/downloads/guaguastandup/zotero-pdf2zh/total?color=yellow)
[![License](https://img.shields.io/github/license/guaguastandup/zotero-pdf2zh)](https://github.com/guaguastandup/zotero-pdf2zh/blob/main/LICENSE)

在Zotero中使用[PDF2zh](https://github.com/Byaidu/PDFMathTranslate)和[PDF2zh_next](https://github.com/PDFMathTranslate/PDFMathTranslate-next)

[使用pdf2zh教程(本页面， Stable)](./README.md) | [使用pdf2zh_next教程(Experimental)](./README_babeldoc.md)

</div>

# 如何使用本插件

本指南将引导您完成 Zotero PDF2zh 插件的安装和配置。

遇到问题：

- 请先访问：[常见问题](https://github.com/guaguastandup/zotero-pdf2zh/issues/64)
- 尝试问一下AI
- 提issue或到插件群发自己的终端报错截图（一定要有终端截图，谢谢！）
- 访问网络上的视频教程，感谢大家的视频教程！
    - 来自小红薯[@jiajia](https://www.xiaohongshu.com/user/profile/631310d8000000001200c3a1?channelType=web_engagement_notification_page&channelTabId=mentions&xsec_token=AB6wOtAu2rBNcN8WfzJS72pVX6rDZYfWMImRRCx98yX6w%3D&xsec_source=pc_notice)的视频教程: [【史上最强PDF文献翻译，zotero-pdf2zh部署 - jiajia | 小红书 - 你的生活指南】](https://www.xiaohongshu.com/discovery/item/684fcb7a0000000022029c73?source=webshare&xhsshare=pc_web&xsec_token=ABNsFW84A-oXoKOuW411myHQThE4BpC0sEJNogkFFSuzg=&xsec_source=pc_share)
    - 来自bilibili[@她笑中藏泪花](https://space.bilibili.com/3493121191054300)的视频教程:[【Zotero-pdf2zh】轻松实现Zotero文献翻译！手把手教你配置pdf2zh插件---PDFMathTranslate](https://www.bilibili.com/video/BV13X9yY9EEH/?share_source=copy_web&vd_source=a492b2fdd5febb228a648d598595ea6e)

## 第一步 安装与启动

有Docker启动和终端启动两种方法可选。

### 方法一：Docker启动

**第一步：创建目录，下载并创建必要文件**

```shell
# 1. 创建并进入docker文件夹
mkdir docker && cd docker
# 2. 下载docker文件
wget https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/2.4.3%20version/Dockerfile
wget https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/2.4.3%20version/docker-compose.yaml
# 3. 创建并进入zotero-pdf2zh文件夹
mkdir zotero-pdf2zh && cd zotero-pdf2zh
# 4. 创建translated文件夹，存放翻译输出文件
mkdir translated
# 5. 创建config.json文件(待配置)
echo '{}' > config.json
# 6. 回到docker文件夹
cd ..
```

文件夹结构如下：

```shell
docker
    ├── Dockerfile
    ├── docker-compose.yaml
    └── zotero-pdf2zh
        ├── config.json
        └── translated
```

**第二步：构建 Docker 镜像**

```shell
docker compose build
```

**第三步：启动 Docker 容器**

- **首次运行（推荐）**：在当前终端启动，以便观察 Docker 容器的输出和翻译是否正常

    ```shell
    docker compose up
    ```

- **后台启动**： 在当前终端启动 Docker 程序，程序将挂载在后台（首次执行建议在终端运行，以便观察 PDF 是否正确翻译）

    ```shell
    docker compose up -d
    ```

### 方法二：本地终端启动

**第一步：创建目录，存放本插件需要的所有文件**

```shell
# 1. 创建并进入zotero-pdf2zh文件夹
mkdir zotero-pdf2zh && cd zotero-pdf2zh
# 2. 下载server.py文件
wget https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/2.4.3%20version/server.py
# 3. 创建translated文件夹，存放翻译输出文件
mkdir translated
# 4. 创建config.json文件(待配置)
echo '{}' > config.json
```

文件夹结构如下：

```shell
zotero-pdf2zh
    ├── config.json
    ├── server.py
    └── translated
```

**第二步：创建虚拟环境并安装需要的包**

安装方式请在 `conda` 或 `uv` 中选择一种即可。

**conda安装**

```shell
conda create -n zotero-pdf2zh python=3.12			# 创建conda虚拟环境
conda activate zotero-pdf2zh						# 启动conda虚拟环境
python -m pip install pdf2zh==1.9.6 flask pypdf     # 安装需要的包
python -m pip install pdfminer.six==20250416        # 修正pdfminer安装版本
python -m pip install numpy==2.2.0
```

**uv安装**

进入`zotero-pdf2zh`文件夹：

1.  安装uv环境

```shell
# 方法一: 使用pip安装uv
pip install uv
# 方法二: 下载脚本安装
# macOS/Linux
wget -qO- https://astral.sh/uv/install.sh | sh
# windows
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

2.  uv安装Python 3.12

```shell
uv python install 3.12  # 安装3.12版本python
uv venv --python 3.12   # 创建3.12版本python虚拟环境
```

3.  启动虚拟环境

- Linux/macOS执行

    ```shell
    source .venv/bin/activate
    ```

- windows执行

    ```shell
    .\.venv\Scripts\activate
    ```

3.  第三步: 安装需要的包

    ```shell
    uv pip install pdf2zh==1.9.6 flask pypdf # 安装需要的包
    uv pip install pdfminer.six==20250416    # 修正pdfminer安装版本
    uv pip install numpy==2.2.0              # 修正numpy安装版本
    ```

**第三步：测试pdf2zh安装**

在终端直接输入命令:

```shell
pdf2zh document.pdf --service bing # document.pdf是待翻译的文件
```

请不要忽略测试步骤。

等待翻译结束，如果失败了，说明上一步的安装出现问题。这一步会使用bing免费服务翻译文件。

本插件当前开发使用的 `pdf2zh`版本: `v1.9.11`.

**第四步：执行Python脚本**

- Conda版本

```shell
python server.py 8888
```

- uv版本

```shell
uv run server.py 8888
```

> **💡Tips**
>
> - 命令行参数 `8888` 是端口号，您可以自行修改，但请确保该端口是开放的。
> - **提示：** 如果在此步骤中修改了端口号，那么在 Zotero 配置中（第三步），也需要相应地修改 **Python 服务器 IP 端口号**。

## 第二步：添加PDF2zh配置文件 & 修改翻译中文字体

**第一步：复制`config.json`模版**

- `config.json`文件示例如下，将此模版替换到第一步中创建的`config.json`文件内容：

```json
{
    "USE_MODELSCOPE": "0",
    "PDF2ZH_LANG_FROM": "English",
    "PDF2ZH_LANG_TO": "Simplified Chinese",
    "NOTO_FONT_PATH": "./LXGWWenKai-Regular.ttf",
    "translators": [
        {
            "name": "deepseek",
            "envs": {
                "DEEPSEEK_API_KEY": "sk-xxxxxxx",
                "DEEPSEEK_MODEL": "deepseek-chat"
            }
        },
        {
            "name": "zhipu",
            "envs": {
                "ZHIPU_API_KEY": "xxxxxx",
                "ZHIPU_MODEL": "glm-4-flash"
            }
        },
        {
            "name": "openailiked",
            "envs": {
                "OPENAILIKED_BASE_URL": "https://ark.cn-beijing.volces.com/api/v3",
                "OPENAILIKED_API_KEY": "xxxxx",
                "OPENAILIKED_MODEL": "ep-xxxx-xxxxx"
            }
        }
    ]
}
```

**第二步：字体配置**

- 将字体文件放在`zotero-pdf2zh`， 然后在`config.json`中，修改自定义字体文件路径`"NOTO_FONT_PATH": "./xxxxxx.xxx"(您的字体文件名)`.

- 如果翻译后无法正确显示字体，请先在电脑中安装本字体.

- 推荐下载并使用 [霞鹜文楷字体 (LXGWWenKai-Regular.ttf)](https://github.com/lxgw/LxgwWenKai/releases/download/v1.510/LXGWWenKai-Regular.ttf) 或 "微信读书AI楷"(可以在贴吧等社区搜索下载).

- 如果使用docker方法启动，并需要自定义字体，需要进行以下步骤：

    1.  在`docker-compose.yaml`文件中挂载字体文件：

    ```shell
    volumes:
        - ./zotero-pdf2zh/translated:/app/translated
        - ./zotero-pdf2zh/config.json:/app/config.json
        - ./zotero-pdf2zh/LXGWWenKai-Regular.ttf:/app/LXGWWenKai-Regular.ttf # 这一行是新添加的字体挂载。
    ```

    2.  执行`docker compose up -d`，更新容器挂载信息。

**第三步：翻译引擎配置**

在`config.json`文件中，将您申请的LLM API和使用的LLM Model配置输入 `translators`中。

> 关于翻译引擎的选择：
>
> - 使用默认的bing或者google，速度快，效果适中，不需要在config.json文件中配置
> - 推荐1：在[火山引擎](https://www.volcengine.com/product/doubao/)中选择`deepseek-v3`模型服务（参与协作奖励计划，每天有50w免费额度，需要将自己的推理内容共享给火山引擎)，线程数可设置为200以上， 此服务对应下方实例文件中的`openailiked`.
> - 推荐2：[智谱AI](https://www.bigmodel.cn/)的`glm-4-flash`模型（免费），此服务对应下方实例文件中的`zhipu`.
> - 推荐3：[deepseek](https://platform.deepseek.com/)的`deepseek-v3`，夜间00:30以后有50%优惠，可以按住shift选择多个条目-右键翻译，并且把线程数调高（20以上），此服务对应下方实例文件中的`deepseek`.

- 更多配置方法，请参考PDF2zh原文档： [PDF2zh Config File](https://github.com/Byaidu/PDFMathTranslate/blob/main/docs/ADVANCED.md#cofig)

## 第三步 在Zotero中配置插件参数

<img src="./images/image1.png" alt="image1" style="width: 600px" align="center"/>

### Step 1.1 设置翻译参数

| 选项             | 值                            | 备注                                                                                                                                                                                          |
| ---------------- | ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Python Server IP | 默认为`http://localhost:8888` | 其中 `8888` 为翻译端口号，需与启动脚本时设置的端口号一致。                                                                                                                                    |
| 源语言           | 默认为`en`                    | 翻译源语言，默认为英文。                                                                                                                                                                      |
| 目标语言         | 默认为`zh`                    | 翻译目标语言，默认为中文。                                                                                                                                                                    |
| 翻译引擎         | `pdf2zh`                      | 目前仅支持 PDF2zh，无需改动。                                                                                                                                                                 |
| 翻译服务         | 默认为`bing`                  | 翻译服务，可以从下拉菜单选择或自行输入。与配置文件 `config.json` 中的 `translators` 对应。（根据需要调整）                                                                                    |
| 线程数           | 默认为`4`                     | PDF2zh在翻译时的执行线程数。（根据需要调整）                                                                                                                                                  |
| 翻译文件输出路径 | 默认为`./translated/`         | 用于临时存储翻译得到的 PDF 文件，翻译完成后可以删除。（无需改动）                                                                                                                             |
| 配置文件路径     | 默认为`./config.json`         | 用于配置翻译引擎和字体。（无需改动）                                                                                                                                                          |
| 重命名为短标题   | 默认勾选                      | 将新增文件的条目标题命名为**短标题**，但是不会改变原文件的命名；<br />**命名规则**：`短标题-翻译类型-翻译服务名`，如果短标题不存在，则命名为`翻译类型-翻译服务名`。例如`vLLM-dual-deepseek`。 |
| 启用babeldoc     | 默认不勾选                    | 是否在PDF2zh中启用`babeldoc`。                                                                                                                                                                |
| 默认生成翻译     | 默认生成mono和dual文件        | 通过勾选来控制添加到 Zotero 中的文件类型。同时，您可以进一步勾选是否在生成该文件后自动打开。临时文件夹中默认生成 `mono`（仅目标语言）和 `dual`（源语言和目标语言）两种文件。                  |
| 跳过子集化       | 默认不勾选                    | **在翻译正常进行但最终渲染 PDF 失败的情况下，可以考虑勾选此项。**                                                                                                                             |
| 跳过最后几页     | 默认值为0                     | 为了节约 LLM 的 token 用量，可以跳过最后几页引用文献不翻译（目前不支持 `babeldoc` 模式，如果使用 `babeldoc` 服务，请将此选项设置为 `0`）。                                                    |

> **💡Tips**
>
> 1.  `dual`文件中包含源语言和目标语言，`mono`文件中仅包含目标语言
> 2.  以上路径支持绝对路径和相对路径。如果设置为相对路径，则根路径与接下来Python脚本执行的路径一致。
>     - 举例：如果python脚本在`/home/xxx/server/`下执行，翻译输出路径设置为临时路径`./translated/`，则实际的输出路径为`/home/xxx/server/translated/`
>     - 一般来说不需要改动本路径，直接使用默认的相对路径即可。

## 第四步 翻译文件

打开Zotero，右键选择条目或者附件。（支持批量选择）
如果选择条目，将会自动选择该条目下创建时间**最早**的PDF。

<img src="./images/image2.png" alt="image2" style="width: 1000px" align="center"/>

**选项一：PDF2zh：翻译PDF**

本选项生成的文件由Zotero插件设置中的“默认生成文件”勾选项决定，默认生成`mono`和`dual`两个文件。

**选项二：PDF2zh：裁剪PDF**

本选项仅将选中的pdf文件由双栏文件切割为单栏文件。

将双栏论文剪切拼接为单栏显示，适配手机阅读

得到后缀中包含`cut`的单栏PDF文件，如`mono-cut`， `dual-cut`，`origin-cut`

**选项三：PDF2zh：双语对照(双栏)**

本选项适用于不启动`babeldoc`选项的情况。

本选项仅将后缀包含`dual`的文件切割拼接为中英文对照文件。

- 如果已有`dual`文件，则对该`dual`附件右键-点击PDF2zh双语对照(双栏)

它会将翻译后的双栏PDF竖向切成两半，然后对裁剪后的单栏进行左右双语拼接。

得到后缀中包含`compare`的双语左右对照PDF文件。

**选项四：PDF2zh：双语对照(单栏)**

本选项适用于不启动`babeldoc`选项的情况。

本选项仅将后缀包含`dual`的文件切割拼接为中英文对照文件。

- 如果已有`dual`文件，则对该`dual`附件右键-点击PDF2zh双语对照(单栏)

它会直接将翻译后的PDF进行左右双语拼接，不切割。

得到后缀中包含`single-compare`的双语左右对照PDF文件。

> **💡Tips**
>
> 如果启用babeldoc，则生成的dual文件等效于双语对照（单栏）

## ✨新功能：macOS中的自动化流程

详见[macOS自动化流程](https://github.com/guaguastandup/zotero-pdf2zh/blob/main/automation/macos/%E6%95%99%E7%A8%8B.md)

- 自动启停：当您打开 Zotero 应用程序时，后台会自动启动 server.py 翻译服务；关闭 Zotero 时，服务也会被自动终止，释放系统资源。

- 稳定守护：在 Zotero 运行期间，如果 server.py 服务因任何原因意外崩溃，后台服务会检测到并在 10 秒内自动重启，确保服务的可用性。

- 静默通知：服务在启动、停止或翻译PDF时，都会通过macOS通知中心发送静默通知，让您能实时了解服务状态和翻译进度，而不会打扰您的工作流程。

- 右键翻译：在MacOS文件目录中右键文件翻译

贡献者[@LinHuanli](https://github.com/LinHuanli)

## 翻译效果展示

<img src="./images/image3.png" alt="image3" style="width: 500px" align="center"/>

<img src="./images/image4-1.png" alt="image4-1" style="width: 500px" align="center"/>

<img src="./images/image4-2.png" alt="image4-2" style="width: 500px" align="center"/>

<img src="./images/image4-3.png" alt="image4-3" style="width: 500px" align="center"/>

# 致谢

- @Byaidu [PDF2zh](https://github.com/Byaidu/PDFMathTranslate)
- @windingwind [zotero-plugin-template](https://github.com/windingwind/zotero-plugin-template)

# 贡献者

<a href="https://github.com/guaguastandup/zotero-pdf2zh/graphs/contributors"> <img src="https://contrib.rocks/image?repo=guaguastandup/zotero-pdf2zh" /></a>

# 💗

欢迎提issue或者参与贡献

提issue前请先阅读本链接：[常见问题](https://github.com/guaguastandup/zotero-pdf2zh/issues/64)

本项目交流QQ群: 971960014 入群口令请到 GitHub / Gitee 仓库主页查看

# Support me

💐免费开源插件，您的支持是我继续开发的动力～

- SiliconFlow邀请链接: https://cloud.siliconflow.cn/i/WLYnNanQ

# TODO LIST

- [ ] 提供共享远程翻译服务（基于SealOS）
- [ ] 支持Obsidian式配置（不需要打开设置页面）
- [ ] 支持Zotero插件页面配置API Key
- [ ] 翻译进度显示
- [ ] 将翻译后的PDF转换为markdown或html
- [x] 支持单栏左右对照和双栏左右对照
- [x] 增加Drop Last功能，跳过引用文献不翻译
- [x] 兼容babeldoc
- [x] 支持远程部署
- [x] 适配[PolyglotPDF](https://github.com/CBIhalsen/PolyglotPDF/tree/main)
    - [参考该issue](https://github.com/guaguastandup/zotero-pdf2zh/issues/67)
- [x] 完善Docker部署文档
- [x] 加入插件市场
- [x] 支持在zotero perference中设置pdf2zh参数
