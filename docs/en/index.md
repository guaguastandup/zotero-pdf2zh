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
      text: v4.1.0 Upgrade Guide
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

::: tip Existing users upgrading to v4.1.0
On the first Server start after upgrading, an existing Python translation environment is detected and the user is asked whether to perform a safe update. Choosing `Y` is recommended. A failed update does not modify the working environment in place.

See [Translation Environment Install & Update](/en/guide/package-update).
:::

## Supported Zotero Versions

[![Zotero 8](https://img.shields.io/badge/Zotero-8-blue?style=flat-square&logo=zotero&logoColor=CC2936)](https://www.zotero.org/download/)

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
