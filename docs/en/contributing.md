# Contributing Guide

Thank you for your interest in Zotero PDF2zh! We welcome contributions in all forms.

::: tip Contribution Types
You can participate in the project by:
- Reporting bugs
- Suggesting new features
- Submitting code improvements
- Improving documentation
- Helping other users solve problems
:::

---

## How to Report Bugs

Before submitting an issue, please search if the same problem already exists.

### Bug Report Template

```markdown
**Problem Description**
Briefly describe the issue you encountered

**Environment Information**
- Operating System:
- Zotero Version:
- Plugin Version:
- Python Version:
- Translation Service:

**Steps to Reproduce**
1.
2.
3.

**Expected Behavior**
Describe what you expected to happen

**Actual Behavior**
Describe what actually happened

**Log Information**
```
Paste relevant logs here
```

**Screenshots**
Add screenshots if necessary
```

---

## How to Submit Code

### Development Environment Setup

1. Fork this repository

2. Clone your fork:
```bash
git clone https://github.com/YOUR_USERNAME/zotero-pdf2zh.git
cd zotero-pdf2zh
```

3. Add upstream repository:
```bash
git remote add upstream https://github.com/guaguastandup/zotero-pdf2zh.git
```

4. Create a new branch:
```bash
git checkout -b feature/your-feature-name
```

### Code Style Guidelines

- Follow the existing code style of the project
- Add necessary comments
- Update relevant documentation
- Ensure code passes tests

### Submit a Pull Request

1. Push your branch:
```bash
git push origin feature/your-feature-name
```

2. Create a Pull Request on GitHub

3. Fill in the PR description template:
```markdown
**Type of Change**
- [ ] Bug fix
- [ ] New feature
- [ ] Code refactoring
- [ ] Documentation update

**Description of Changes**
Describe your changes

**Related Issues**
Closes #issue_number
```

---

## Documentation Contributions

Documentation is located in the `docs` directory and built with VitePress.

### Editing Documentation

1. Edit the corresponding Markdown file
2. Preview locally:
```bash
cd docs
npm run docs:dev
```
3. Commit your changes

---

## Community Code of Conduct

- Respect different viewpoints and experiences
- Use friendly and inclusive language
- Accept constructive criticism gracefully
- Focus on what is best for the community
- Show empathy towards other community members

---

## Get Help

- 💬 Join [QQ Group](https://github.com/guaguastandup/zotero-pdf2zh): Group 5: 1064435415, Group 6: 1083772600 (Answer: github)
- 📖 Check [FAQ](/en/guide/faq/)
- 🐛 [Submit an Issue](https://github.com/guaguastandup/zotero-pdf2zh/issues)

---

## TODO List

::: warning Development Notes
The following features are being planned or already have implementation plans. Please do not develop them independently to avoid conflicts with project planning.
:::

### Pending Tasks

| Status | Feature | Notes |
|--------|---------|-------|
| ⏳ | HTML translation page (with candidates) | Under planning |
| ⏳ | Add thread_num parameter for services | Performance optimization |
| ⏳ | Add Command+, shortcut key to README | Documentation update |
| ⏳ | Add dropdown for URL in LLMEditor | UI improvement |
| ⏳ | Extra field settings issue | Configuration optimization |
| ⏳ | Preserve original service for dual-cut based files | Logic improvement |

### Completed

| Status | Feature |
|--------|---------|
| ✅ | Windows terminal emoji display issue |
| ✅ | Automatic server.zip update command |
| ✅ | Table field length adjustment |

### Not Planned

| Status | Feature | Reason |
|--------|---------|--------|
| ❌ | llmapi-table double-click popup | Not implementing at this time |

::: tip Suggestion
If you have new feature suggestions, please submit a [Feature Request](https://github.com/guaguastandup/zotero-pdf2zh/issues) first for discussion to avoid duplicate development.
:::

---

## Active Contributor Rewards

This project partners with [Immersive Translate](https://immersivetranslate.com) to provide monthly Pro membership redemption codes for active contributors.

Details: [CONTRIBUTOR_REWARD.md](https://github.com/funstory-ai/BabelDOC/blob/main/docs/CONTRIBUTOR_REWARD.md)

---

## Acknowledgments

Thanks to all developers who have contributed to this project! Every PR, Issue, and comment makes this project better.

<a href="https://github.com/guaguastandup/zotero-pdf2zh/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=guaguastandup/zotero-pdf2zh" alt="Contributors"/>
</a>
