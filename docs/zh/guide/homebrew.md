# Homebrew 部署

使用 Homebrew 在 macOS/Linux 上部署 Zotero PDF2zh 服务。

::: tip Homebrew 优势
- 包管理自动化，安装和更新更方便
- 自动处理依赖关系
- 适合熟悉 Homebrew 的用户
:::

::: warning 注意
此部署方式由社区贡献者维护，非官方维护。
:::

---

## 前置要求

确保已安装 Homebrew：

```bash
brew --version
```

### 安装 Homebrew

**macOS:**

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

**Linux:**

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
```

---

## 安装服务

```bash
brew install zotero-pdf2zh-server
```

此命令会自动：
- 安装 Python 依赖
- 配置服务环境
- 设置可执行命令

---

## 启动服务

安装完成后，有两种启动方式：

### 方式一：直接命令启动

```bash
zotero-pdf2zh-server
```

### 方式二：作为服务启动

```bash
# 启动服务
brew services start zotero-pdf2zh-server

# 查看服务状态
brew services list

# 停止服务
brew services stop zotero-pdf2zh-server
```

服务默认运行在 `http://127.0.0.1:8890`

---

## 配置端口

如果需要修改端口：

```bash
zotero-pdf2zh-server --port=9999
```

---

## 查看日志

```bash
# 实时查看日志
brew services log zotero-pdf2zh-server --tail -f

# 查看所有日志
brew services log zotero-pdf2zh-server
```

---

## 更新服务

```bash
brew upgrade zotero-pdf2zh-server
```

---

## 卸载

```bash
# 停止服务
brew services stop zotero-pdf2zh-server

# 卸载
brew uninstall zotero-pdf2zh-server

# 清理配置（可选）
rm -rf ~/Library/Application\ Support/zotero-pdf2zh-server
```

---

## 配置 Zotero 插件

1. 打开 Zotero 「工具 → PDF2zh 首选项」

2. 设置 **Python Server IP**: `http://127.0.0.1:8890`

3. 选择 **翻译引擎**: `pdf2zh` 或 `pdf2zh_next`

4. 配置 **LLM API**（详见 [配置说明](/zh/guide/configuration)）

---

## 项目信息

- **仓库地址**: [NightWatcher314/zotero-pdf2zh-server](https://github.com/NightWatcher314/zotero-pdf2zh-server)
- **贡献者**: [@NightWatcher314](https://github.com/NightWatcher314)

---

## 对比其他部署方式

| 方式 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| **Homebrew** | 自动化管理，更新方便 | 仅限 macOS/Linux | 熟悉 Homebrew 的用户 |
| **Docker** | 环境隔离，可移植性强 | 需要 Docker 环境 | 需要频繁切换环境 |
| **源码安装** | 灵活，可定制 | 需要手动管理依赖 | 开发者和高级用户 |

---

## 故障排除

### 服务启动失败

```bash
# 查看详细日志
brew services log zotero-pdf2zh-server --tail -f
```

### 端口被占用

```bash
# 查看 8890 端口占用
lsof -i :8890

# 使用其他端口启动
zotero-pdf2zh-server --port=9999
```

### 依赖问题

```bash
# 重新安装
brew reinstall zotero-pdf2zh-server
```

---

## 下一步

- [配置说明](/zh/guide/configuration) - 插件和服务配置
- [常见问题](/zh/guide/faq/) - 遇到问题？
