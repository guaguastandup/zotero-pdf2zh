---
layout: home

hero:
  name: "Zotero PDF2zh"
  text: "Translate PDFs using PDF2zh and PDF2zh_next in Zotero"
  tagline: A Zotero plugin for PDF translation with format preservation
  image:
    src: /favicon.svg
    alt: Zotero PDF2zh
  actions:
    - theme: brand
      text: Get Started
      link: /en/guide/installation
    - theme: alt
      text: v4.1.1 Upgrade Guide
      link: /en/guide/package-update
    - theme: alt
      text: Configuration
      link: /en/guide/configuration

features:
  - title: 🧠 DeepSeek V4
    details: Supports deepseek-v4-flash / deepseek-v4-pro with explicit Thinking controls; PDF translation defaults to Thinking disabled.
  - title: 🔄 Safe Environment Updates
    details: Keeps existing uv/conda environments and uses staging, validation, switching and rollback protection for Python translation updates.
  - title: 📄 PDF State Management
    details: Correct LR/TB, Crop, Compare and Crop-Compare transitions, with terminal-result guards against repeated processing.
  - title: 🌐 Multiple Services
    details: Supports OpenAI-compatible providers, DeepSeek, Zhipu, Aliyun and more, including model-list fetching for supported providers.
  - title: 🔐 Safer Defaults
    details: Server binds to localhost by default, upload filenames are validated, and API keys/tokens are masked in logs.
  - title: ⚙️ Configuration Migration
    details: Existing user values and custom fields are preserved instead of being overwritten from example files on every startup.
  - title: 📦 Release-built Artifacts
    details: The XPI and server.zip are built from the tagged source during release, avoiding stale static packages.
  - title: 🎯 Zotero Integration
    details: Integrated into Zotero context menus with batch processing and Chinese/English UI support.

---

::: tip v4.1.1 hotfix
Windows Conda users should upgrade to v4.1.1 before starting the Server. v4.1.0 could treat a healthy Conda environment as missing Python. This release looks up `<env>\\python.exe` correctly; if a staging update fails and the previous environment is still healthy, translation keeps using that environment.

After upgrading the Server, the first launch still asks whether to refresh the translation environment. Choosing `Y` is recommended. Do not run `pip install --upgrade` inside the live environment.

See [Translation Environment Install & Update](/en/guide/package-update).
:::

## Supported Zotero Versions

[![Zotero 7](https://img.shields.io/badge/Zotero-7-red?style=flat-square&logo=zotero&logoColor=CC2936)](https://www.zotero.org)
[![Zotero 8](https://img.shields.io/badge/Zotero-8-orange?style=flat-square&logo=zotero&logoColor=CC2936)](https://www.zotero.org/support/beta_builds)
[![Zotero 9](https://img.shields.io/badge/Zotero-9-yellow?style=flat-square&logo=zotero&logoColor=CC2936)](https://www.zotero.org/support/beta_builds)
[![Zotero 10](https://img.shields.io/badge/Zotero-10-green?style=flat-square&logo=zotero&logoColor=CC2936)](https://www.zotero.org/support/beta_builds)

## Quick Links

- [Installation](/en/guide/installation)
- [Configuration](/en/guide/configuration)
- [Translation Options](/en/guide/translation-options)
- [Extra Parameters](/en/guide/extra-params)
- [Translation Environment Updates](/en/guide/package-update)
- [FAQ](/en/guide/faq/)

## Get Help

- [GitHub Issues](https://github.com/guaguastandup/zotero-pdf2zh/issues)
- For community group information, see the latest project README.
