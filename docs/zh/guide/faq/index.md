# 常见问题（FAQ）

::: tip 提问前请阅读
确保已经阅读过常见问题。确定问题为新问题后，将终端报错复制到 txt 文件，并截图 Zotero 插件设置端配置。
:::

---

## 📋 问题索引

按问题类型快速查找：

### 安装相关
- [虚拟环境问题](./virtual-env.md) - conda/uv 安装、路径问题
- [环境配置问题](./environment.md) - DLL 错误、Python 版本、路径问题
- [网络问题](./network.md) - 端口占用、下载失败、连接问题

### 配置相关
- [翻译服务问题](./translation-service.md) - API 配置、Token 消耗、服务选择

### 功能相关
- [插件功能问题](./plugin-features.md) - 翻译选项、OCR、功能说明

### 提问相关
- [有效提问指南](./asking-questions.md) - 如何正确提问

---

## 🎯 按使用阶段查找

不确定自己处于什么阶段？请根据当前情况选择：

---

### 阶段 1：准备安装

**正在做什么**：准备开始安装插件

**常见问题**：
- 需要什么前置条件？
  - Python 3.12.0 - [下载](https://www.python.org/downloads/)
  - Zotero 8 - [下载](https://www.zotero.org/download/)
- Windows 用户需要管理员权限吗？
  - 是，请使用管理员身份运行 cmd.exe

**继续**：[安装指南](../installation)

---

### 阶段 2：安装中

**正在做什么**：正在安装 Python 虚拟环境或下载文件

**常见问题**：
- uv/conda 安装后命令不识别 → [虚拟环境问题](./virtual-env.md#condauv-安装后命令不识别)
- server.zip 下载失败 → [网络问题](./network.md#serverzip-下载失败)
- Python 版本不兼容 → [环境配置问题](./environment.md#python-版本不兼容)

---

### 阶段 3：启动服务

**正在做什么**：运行 `python server.py` 或 Docker 容器

**常见问题**：
- 服务启动失败 → [环境配置问题](./environment.md)
- 端口被占用 (8890) → [网络问题](./network.md#networkerror-when-attempting-to-fetch-resource-)
- DLL 初始化失败 → [环境配置问题](./environment.md#动态链接库dll初始化例程失败)

---

### 阶段 4：安装插件

**正在做什么**：在 Zotero 中安装 xpi 插件

**常见问题**：
- 插件安装后无反应 → 重启 Zotero
- 插件版本不兼容 → 确保使用 Zotero 8 和插件 v3.0.x

---

### 阶段 5：配置翻译

**正在做什么**：配置 API Key 和翻译服务

**常见问题**：
- 没配置 API 可以用吗？ → [翻译服务问题](./translation-service.md#没配置-api-可以用吗)
- 如何选择翻译服务？ → [翻译服务问题](./translation-service.md#如何选择翻译服务)
- API Key 配置后仍报错 → [翻译服务问题](./translation-service.md#api-key-配置后仍然报错)

---

### 阶段 6：开始翻译

**正在做什么**：第一次尝试翻译 PDF

**常见问题**：
- 翻译卡住不动 → [网络问题](./network.md#翻译卡在某个地方不动)
- 扫描版 PDF 翻译失败 → [插件功能问题](./plugin-features.md#scanned-pdf-detected-翻译失败)
- 翻译质量不满意 → [翻译服务问题](./translation-service.md#翻译质量不满意)

---

### 阶段 7：遇到错误

**正在做什么**：使用过程中出现错误提示

**快速排查步骤**：

1. **查看终端错误**
   - 终端中的错误信息通常包含关键线索
   - 复制完整错误信息到文本文件

2. **搜索文档**
   - 使用 Ctrl+F / Cmd+F 在本文档中搜索错误关键词
   - 查看 [问题索引](#-问题索引) 中的相关分类

3. **尝试以下方案**
   - 切换端口：`python server.py --port=9999`
   - 重启服务：停止并重新运行 `python server.py`
   - 检查配置：确认 API Key 和 URL 正确

4. **仍未解决**
   - 阅读 [有效提问指南](./asking-questions.md)
   - 在 [GitHub Issues](https://github.com/guaguastandup/zotero-pdf2zh/issues) 提问
   - 加入 QQ 群：5群 1064435415（入群答案：github）

---

## 🔍 常见错误码速查

| 错误信息 | 可能原因 | 解决方案 |
|----------|----------|----------|
| `NetworkError` | 端口占用或防火墙 | [网络问题](./network.md) |
| `DLL initialization failed` | 缺少 VC++ 运行库 | [环境配置问题](./environment.md) |
| `Failed to canonicalize` | 虚拟环境路径问题 | [虚拟环境问题](./virtual-env.md) |
| `Scanned PDF detected` | 需要先 OCR 处理 | [插件功能问题](./plugin-features.md) |
| `API Key is Required` | 未配置或未激活 API | [翻译服务问题](./translation-service.md) |

---

## 获取更多帮助

- 💬 [GitHub Issues](https://github.com/guaguastandup/zotero-pdf2zh/issues)
- 👥 QQ 群：5群 1064435415（入群答案：github）
