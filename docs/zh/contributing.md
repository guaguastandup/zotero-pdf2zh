# 贡献指南

感谢您对 Zotero PDF2zh 项目的关注！欢迎各种形式的贡献。

::: tip 贡献类型
您可以通过以下方式参与项目：
- 报告 Bug
- 提出新功能建议
- 提交代码改进
- 完善文档
- 帮助其他用户解决问题
:::

---

## 如何报告 Bug

提交 Issue 前，请先搜索是否已有相同问题。

### Bug 报告模板

```markdown
**问题描述**
简要描述遇到的问题

**环境信息**
- 操作系统：
- Zotero 版本：
- 插件版本：
- Python 版本：
- 翻译服务：

**重现步骤**
1.
2.
3.

**预期行为**
描述您期望发生的情况

**实际行为**
描述实际发生的情况

**日志信息**
```
粘贴相关日志
```

**截图**
如有必要，请添加截图
```

---

## 如何提交代码

### 开发环境设置

1. Fork 本仓库

2. 克隆您的 Fork：
```bash
git clone https://github.com/YOUR_USERNAME/zotero-pdf2zh.git
cd zotero-pdf2zh
```

3. 添加上游仓库：
```bash
git remote add upstream https://github.com/guaguastandup/zotero-pdf2zh.git
```

4. 创建新分支：
```bash
git checkout -b feature/your-feature-name
```

### 代码规范

- 遵循项目现有代码风格
- 添加必要的注释
- 更新相关文档
- 确保代码通过测试

### Server 离线测试

从仓库根目录创建测试环境，不使用 Server 托管的翻译环境：

```bash
uv venv .venv-test --python 3.12
uv pip install --python .venv-test/bin/python -r server/requirements.txt
PYTHONPATH=server .venv-test/bin/python -m unittest discover -s server/tests
```

`test_wenyi_core_contract.py` 还要求在该测试环境安装兼容的 `wenyi-cli` 和
`wenyi-core`，否则会跳过这些用例。可在测试环境安装 `wenyi-cli`，也可从 Wenyi
源码仓库安装两个包：

```bash
uv pip install --python .venv-test/bin/python -e /path/to/wenyi/packages/core -e /path/to/wenyi/packages/cli
PYTHONPATH=server .venv-test/bin/python -m unittest discover -s server/tests -p test_wenyi_core_contract.py
```

这些契约用真实 CLI/Core、FakeClient、离线分词器、合成 PDF 和本机假 HTTP 服务，
无需 BabelDOC、API Key、付费服务或用户文档；覆盖检查点复用、换端口、session 缺失、
独立回执与 Core 跨进程锁。Windows 下使用 `.venv-test\Scripts\python.exe`，
并在当前 shell 设置 `PYTHONPATH=server`。

### 提交 Pull Request

1. 推送您的分支：
```bash
git push origin feature/your-feature-name
```

2. 在 GitHub 上创建 Pull Request

3. 填写 PR 描述模板：
```markdown
**更改类型**
- [ ] Bug 修复
- [ ] 新功能
- [ ] 代码重构
- [ ] 文档更新

**更改说明**
描述您的更改内容

**相关 Issue**
关闭 #issue_number
```

---

## 文档贡献

文档位于 `docs` 目录，使用 VitePress 构建。

### 修改文档

1. 编辑对应的 Markdown 文件
2. 本地预览：
```bash
cd docs
npm run docs:dev
```
3. 提交更改

---

## 社区行为准则

- 尊重不同观点和经验
- 使用友好和包容的语言
- 优雅地接受建设性批评
- 关注对社区最有利的事情
- 对其他社区成员表示同理心

---

## 获取帮助

- 💬 加入 [QQ 群](https://github.com/guaguastandup/zotero-pdf2zh)：5群 1064435415、6群 1083772600（入群口令请到 GitHub / Gitee 仓库主页查看）
- 📖 查看 [常见问题](/zh/guide/faq/)
- 🐛 [提交 Issue](https://github.com/guaguastandup/zotero-pdf2zh/issues)

---

## TODO 列表

::: warning 开发注意事项
以下功能正在规划中或已有实现方案，请勿自行开发，以免与项目规划冲突。
:::

### 待办事项

| 状态 | 功能描述 | 备注 |
|------|---------|------|
| ⏳ | HTML 翻译页面（包含候选项） | 功能规划中 |
| ⏳ | 服务添加对应的 thread_num 参数 | 性能优化 |
| ⏳ | README 增加 Command+, 快捷键说明 | 文档更新 |
| ⏳ | LLMEditor 的 URL 增加下拉选择框 | UI 改进 |
| ⏳ | 额外字段的设置问题 | 配置优化 |
| ⏳ | 基于 dual-cut 生成的文件保持原 service | 逻辑改进 |

### 已完成

| 状态 | 功能描述 |
|------|---------|
| ✅ | Windows 终端显示表情问题 |
| ✅ | 自动更新 server.zip 的命令 |
| ✅ | 表格字段长度调整 |

### 暂不开发

| 状态 | 功能描述 | 原因 |
|------|---------|------|
| ❌ | llmapi-table 双击条目弹出弹窗 | 暂不实现 |

::: tip 建议
如果您有新功能建议，请先提交 [Feature Request](https://github.com/guaguastandup/zotero-pdf2zh/issues) 讨论，避免重复开发。
:::

---

## 活跃贡献者奖励

本项目与 [沉浸式翻译](https://immersivetranslate.com) 合作，为活跃贡献者提供每月 Pro 会员兑换码奖励。

详情见：[CONTRIBUTOR_REWARD.md](https://github.com/funstory-ai/BabelDOC/blob/main/docs/CONTRIBUTOR_REWARD.md)

---

## 致谢

感谢所有为本项目做出贡献的开发者！您的每一个 PR、Issue 和评论都让这个项目变得更好。

<a href="https://github.com/guaguastandup/zotero-pdf2zh/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=guaguastandup/zotero-pdf2zh" alt="Contributors"/>
</a>
