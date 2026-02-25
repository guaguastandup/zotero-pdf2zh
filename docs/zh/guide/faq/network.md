# 网络问题

关于网络连接、端口占用、下载卡顿等问题。

---

## NetworkError when attempting to fetch resource 🔥

### 问题描述

翻译时提示 "NetworkError when attempting to fetch resource" 或类似网络错误。

### 原因

1. 插件版本过旧
2. server.py 脚本未运行
3. 端口被占用或防火墙阻止
4. 杀毒软件拦截

### 解决方案

请按以下顺序逐步排查：

1. **确保插件是最新版**
   - 版本号应该是 3.0.x，而不是旧版本 2.4.3
   - 在 Zotero 中检查更新或重新下载最新 xpi 文件

2. **确保 server.py 脚本正在运行**
   - 翻译过程中需要保证 server.py 脚本开启
   - 检查终端是否有输出日志

3. **检查端口是否被占用**
   - 默认端口 8890 可能被其他程序占用
   - 使用以下命令检查端口：
     ```shell
     # macOS/Linux
     lsof -i :8890
     # Windows
     netstat -ano | findstr :8890
     ```

4. **切换端口重试**
   - 可以多次尝试更换新的端口（如 9999、8888 等）
   - 切换端口需要修改两个地方：
     - Zotero 插件配置里的 "Python Server IP" 中的 `:8890` 修改为 `:9999`
     - 执行脚本时的指令修改为：`python server.py --port=9999`

5. **检查防火墙**
   - 确保防火墙允许 Python 访问网络
   - Windows：允许 Python 通过 Windows 防火墙
   - macOS：系统偏好设置 → 安全性与隐私 → 防火墙选项

6. **关闭杀毒软件并重启电脑**
   - 某些杀毒软件会拦截 Python 的网络请求
   - 临时关闭杀毒软件测试

7. **检查终端日志**
   - 如果执行翻译时终端有日志输出/正在尝试翻译，此后报网络错误
   - 应该优先解决终端中提示的具体报错，而不是网络问题

---

## 翻译卡在某个地方不动 🔥

### 问题描述

翻译进度条卡在某个位置（如 10/100）不动，或者长时间没有响应。

### 原因

pdf2zh_next 在首次启动时，需要远程下载字体和模型文件，这个过程比较慢。下载的文件包括：
- BabelDOC 资源文件
- 字体文件
- OCR 模型（如果使用）

### 解决方案

1. **用预热模式，继续等待下载**
   - 首次下载可能需要 10-30 分钟，取决于网络速度
   - 请保持耐心等待，不要关闭终端

2. **手动下载资源文件**
   - 访问 [pdf2zh_next 最新 release](https://github.com/PDFMathTranslate/PDFMathTranslate-next/releases)
   - 下载其中的 exe 包，例如：`pdf2zh-v2.6.4-BabelDOC-xxx-with-assets-win64.zip`
   - 如果由于网络问题无法下载，请加入 QQ 群下载群文件
   - 解压后打开其中的 pdf2zh.exe
   - 浏览器会自动打开 GUI 页面（`http://127.0.0.1:7860/`）
   - 在 GUI 中翻译一篇文章后退出
   - 回到 Zotero 插件重新翻译

3. **检查网络连接**
   - 确保网络连接正常
   - 如果在国内，可能需要使用镜像源

---

## 预热步骤卡住

### 问题描述

使用 `--warmup` 参数时，卡在 warmup 步骤不动。

### 原因

与"翻译卡在某个地方不动"相同，是因为需要下载 babeldoc 的资源文件。

### 解决方案

见上方"翻译卡在某个地方不动"的解决方案。

---

## 第一次翻译时进度条一直卡在某一处

### 问题描述

没使用预热方法，在 pdf2zh_next 的第一次翻译时，进度条一直卡在某一处（如 10/100），或出现 "assets download failed" 的问题。

### 原因

pdf2zh_next 首次翻译需要下载字体和模型文件。

### 解决方案

见上方"翻译卡在某个地方不动"的解决方案。

---

## server.zip 下载失败

### 问题描述

使用 wget 下载 server.zip 时下载失败。

### 原因

网络连接问题或 GitHub 访问受限。

### 解决方案

1. **手动下载**
   - 直接访问 [server.zip](https://github.com/guaguastandup/zotero-pdf2zh/blob/main/server.zip)
   - 点击页面右上角的 "Download" 按钮
   - 将下载的文件移动到 zotero-pdf2zh 文件夹
   - 手动解压：
     ```shell
     # macOS/Linux
     unzip server.zip
     # Windows
     # 右键解压或使用以下命令
     tar -xf server.zip
     ```

2. **使用镜像源**
   - 尝试使用 gitee 镜像源（如果可用）

3. **使用代理**
   - 如果网络受限，可以配置代理后重试

---

## bing/google 翻译报错或中止 🔥

### 问题描述

使用 bing/google 免费翻译服务时，翻译到一半就报错/卡住/中止。

### 原因

bing 和 google 的翻译服务都存在**限流**，当请求频率过高时会拒绝服务。

### 解决方案

1. **降低并发数**
   - 将插件设置中的并发数设置得非常低（建议 2 及以下）
   - 将 QPS 设置为 1 或更低

2. **更换翻译服务**
   - bing/google 的限流较为严重，不适合长期使用
   - 建议使用更加稳定的服务：
     - [siliconflowfree](/zh/guide/configuration.md#siliconflowfree) - 免费但可能漏翻译
     - [deepseek](/zh/guide/configuration.md#deepseek) - 翻译效果好，有缓存机制
     - 其他付费服务

::: tip 建议
为了获得更好的翻译体验和稳定性，建议配置自己的 API Key 使用付费服务或硅基流动免费服务。
:::
