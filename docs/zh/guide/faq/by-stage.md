# 按使用阶段查找

不确定自己处于什么阶段？请根据当前情况选择：

---

## 阶段 1：准备安装 🔧

**正在做什么**：准备开始安装插件

**需要准备**：
- [Python 3.12.0](https://www.python.org/downloads/)
- [Zotero 8](https://www.zotero.org/download/)
- Windows 用户需要管理员权限

**下一步**：[安装指南](../installation)

---

## 阶段 2：安装中 📦

**正在做什么**：正在安装 Python 虚拟环境或下载文件

**常见问题**：

| 问题 | 解决方案 |
|------|----------|
| uv/conda 安装后命令不识别 | [虚拟环境问题 →](./virtual-env.md#condauv-安装后命令不识别) |
| server.zip 下载失败 | [网络问题 →](./network.md#serverzip-下载失败) |
| Python 版本不兼容 | [环境配置问题 →](./environment.md#python-版本不兼容) |

---

## 阶段 3：启动服务 🚀

**正在做什么**：运行 `python server.py` 或 Docker 容器

**常见问题**：

| 问题 | 解决方案 |
|------|----------|
| 服务启动失败 | [环境配置问题 →](./environment.md) |
| 端口被占用 (8890) | [网络问题 →](./network.md#networkerror-when-attempting-to-fetch-resource-) |
| DLL 初始化失败 | [环境配置问题 →](./environment.md#动态链接库dll初始化例程失败) |

**检查清单**：
- [ ] server.py 正在运行
- [ ] 终端显示 "Running on http://127.0.0.1:8890"
- [ ] 浏览器可以访问 http://127.0.0.1:8890

---

## 阶段 4：安装插件 🔌

**正在做什么**：在 Zotero 中安装 xpi 插件

**步骤**：
1. 下载 [v3.0.37](https://github.com/guaguastandup/zotero-pdf2zh/releases/download/v3.0.37/zotero-pdf-2-zh.xpi)
2. 打开 Zotero 「工具 → 插件」
3. 将 xpi 文件拖入插件窗口
4. 重启 Zotero

**常见问题**：
- 插件安装后无反应 → 重启 Zotero
- 插件版本不兼容 → 确保使用 Zotero 8 和插件 v3.0.x

---

## 阶段 5：配置翻译 ⚙️

**正在做什么**：配置 API Key 和翻译服务

**常见问题**：

| 问题 | 解决方案 |
|------|----------|
| 没配置 API 可以用吗？ | [翻译服务问题 →](./translation-service.md#没配置-api-可以用吗) |
| 如何选择翻译服务？ | [翻译服务问题 →](./translation-service.md#如何选择翻译服务) |
| API Key 配置后仍报错 | [翻译服务问题 →](./translation-service.md#api-key-配置后仍然报错) |

**检查清单**：
- [ ] Python Server IP 设置为 `http://127.0.0.1:8890`
- [ ] 已选择翻译引擎 (pdf2zh 或 pdf2zh_next)
- [ ] 已配置或激活 LLM API

---

## 阶段 6：开始翻译 📄

**正在做什么**：第一次尝试翻译 PDF

**常见问题**：

| 问题 | 解决方案 |
|------|----------|
| 翻译卡住不动 | [网络问题 →](./network.md#翻译卡在某个地方不动) |
| 扫描版 PDF 翻译失败 | [插件功能问题 →](./plugin-features.md#scanned-pdf-detected-翻译失败) |
| 翻译质量不满意 | [翻译服务问题 →](./translation-service.md#翻译质量不满意) |
| bing/google 中途报错 | [网络问题 →](./network.md#binggoogle-翻译报错或中止) |

**检查清单**：
- [ ] server.py 终端有日志输出
- [ ] Zotero 右键菜单可以看到 PDF2zh 选项
- [ ] 可以看到翻译进度

---

## 阶段 7：遇到错误 ❌

**正在做什么**：使用过程中出现错误提示

**快速排查步骤**：

### 1. 查看终端错误

终端中的错误信息通常包含关键线索：

**示例 1**：
```
DeepSeek API Key is Required
```
**含义**：没有配置 DeepSeek API Key
**解决**：[翻译服务问题](./translation-service.md)

**示例 2**：
```
OSError: Microsoft Visual C++ Redistributable is not installed
```
**含义**：缺少 Visual C++ 运行库
**解决**：[环境配置问题](./environment.md#动态链接库dll初始化例程失败)

**示例 3**：
```
Failed to canonicalize script path
```
**含义**：虚拟环境路径问题
**解决**：[虚拟环境问题](./virtual-env.md#failed-to-canonicalize-script-path)

### 2. 搜索文档

使用 Ctrl+F / Cmd+F 在本文档中搜索错误关键词。

### 3. 尝试基础解决方案

```shell
# 切换端口
python server.py --port=9999

# 重启服务
# 停止当前服务，重新运行
python server.py
```

### 4. 仍未解决

- 阅读 [有效提问指南](./asking-questions.md)
- 在 [GitHub Issues](https://github.com/guaguastandup/zotero-pdf2zh/issues) 提问
- 加入 QQ 群：5群 1064435415（入群答案：github）

---

## 📊 问题解决流程图

```
遇到问题
    ↓
查看终端错误信息
    ↓
搜索本文档
    ↓
┌─────────────┬─────────────┬─────────────┐
↓             ↓             ↓             ↓
安装相关     配置相关     功能相关     其他问题
    ↓             ↓             ↓             ↓
[安装指南]   [配置说明]   [功能说明]   [GitHub Issues]
```

---

## 🔍 常见错误码速查

| 错误信息 | 可能原因 | 快速解决 |
|----------|----------|----------|
| `NetworkError` | 端口/防火墙 | 切换端口到 9999 |
| `DLL initialization failed` | 缺少 VC++ | [安装 VC++ 运行库](https://aka.ms/vs/17/release/vc_redist.x64.exe) |
| `Failed to canonicalize` | 移动了 server 文件夹 | 重新安装或删除虚拟环境文件夹 |
| `Scanned PDF detected` | 需要先 OCR | 用其他工具 OCR 后再翻译 |
| `API Key is Required` | 未配置 API | 配置并激活 API Key |
| `command not found: uv` | uv 未加入 PATH | 重新打开终端或手动加入 PATH |

---

## 获取帮助

- 💬 [GitHub Issues](https://github.com/guaguastandup/zotero-pdf2zh/issues)
- 👥 QQ 群：5群 1064435415（入群答案：github）
- 📋 [问题索引](./index.md) - 按类型查找问题
