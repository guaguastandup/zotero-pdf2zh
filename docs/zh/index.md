---
layout: home

hero:
  name: "Zotero PDF2zh"
  text: ""
  tagline: 完美保留原文格式的 Zotero PDF 翻译插件
  image:
    src: ../favicon.svg
    alt: Zotero PDF2zh
  actions:
    - theme: brand
      text: 快速开始
      link: /zh/guide/installation
    - theme: alt
      text: v4.1.0 升级说明
      link: /zh/guide/package-update
    - theme: alt
      text: 配置说明
      link: /zh/guide/configuration

features:
  - title: 🧠 DeepSeek V4
    details: 支持 deepseek-v4-flash / deepseek-v4-pro，可显式关闭或开启 Thinking；PDF 翻译默认关闭 Thinking。
  - title: 🔄 安全环境更新
    details: 自动沿用已有 uv/conda；通过 staging 安装、验证、切换和回滚保护更新 Python 翻译环境。
  - title: 📄 PDF 状态管理
    details: 正确处理 LR/TB、Crop、Compare、Crop-Compare，阻止终态 PDF 被重复加工。
  - title: 🌐 多服务支持
    details: 支持 OpenAI 兼容格式、DeepSeek、智谱、阿里云等多种翻译服务，并可获取部分服务的模型列表。
  - title: 🔐 更安全的默认值
    details: Server 默认只监听 localhost，上传路径校验加强，API Key / token 日志自动脱敏。
  - title: ⚙️ 配置迁移
    details: 更新后保留用户配置和自定义字段，不再每次启动用 example 文件覆盖用户设置。
  - title: 📦 Release 安装包
    details: 插件 XPI 与 server.zip 由 Release 流程根据当前 tag 构建，避免静态安装包和源码不同步。
  - title: 🎯 Zotero 集成
    details: 集成到 Zotero 右键菜单，支持批量翻译和中英文界面。

---

::: tip v4.1.0 已有用户升级
升级 Server 后首次启动会检测已有 Python 翻译环境，并询问是否安全更新。建议选择 `Y`。更新失败不会原地破坏旧环境。

详见 [翻译环境安装与更新](/zh/guide/package-update)。
:::

## 支持的 Zotero 版本

[![Zotero 8](https://img.shields.io/badge/Zotero-8-blue?style=flat-square&logo=zotero&logoColor=CC2936)](https://www.zotero.org/download/)

## 快速链接

- [安装指南](/zh/guide/installation)
- [配置说明](/zh/guide/configuration)
- [翻译选项](/zh/guide/translation-options)
- [额外参数](/zh/guide/extra-params)
- [翻译环境更新](/zh/guide/package-update)
- [常见问题](/zh/guide/faq/)

## 获取帮助

- [GitHub Issues](https://github.com/guaguastandup/zotero-pdf2zh/issues)
- QQ 群信息请以项目 GitHub 首页最新说明为准。

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=guaguastandup/zotero-pdf2zh&type=Date)](https://star-history.com/#guaguastandup/zotero-pdf2zh&Date)
