# Quick Start

This guide will help you quickly install and configure Zotero PDF2zh plugin.

## Prerequisites

Before you begin, make sure you have:

- [Python 3.12.0](https://www.python.org/downloads/)
- [Zotero 7](https://www.zotero.org/download/) or [Zotero 8](https://www.zotero.org/support/beta_builds)

::: tip Note
Windows users should run cmd.exe as **administrator**.
:::

---

## Quick Installation (Recommended)

### Step 1: Install uv

```shell
# macOS/Linux
wget -qO- https://astral.sh/uv/install.sh | sh

# Windows (in PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Step 2: Download and Setup

```shell
# Create project folder
mkdir zotero-pdf2zh && cd zotero-pdf2zh

# Download and extract server
wget https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/server.zip
unzip server.zip

# Enter server folder
cd server

# Install dependencies and start
pip install -r requirements.txt
python server.py
```

### Step 3: Install Plugin

1. Download the latest plugin: [v4.0.0](https://github.com/guaguastandup/zotero-pdf2zh/releases/download/v4.0.0/zotero-pdf-2-zh.xpi)
2. In Zotero, open "Tools → Add-ons"
3. Drag the xpi file into the add-ons window
4. Restart Zotero if needed

### Step 4: Configure

1. Open "Tools → PDF2zh Preferences"
2. Configure your translation service
3. Click "Check Connection" to verify

---

## Next Steps

- [Full Installation Guide](/en/guide/installation) - Detailed installation instructions
- [Configuration](/en/guide/configuration) - Plugin and service configuration
- [FAQ](/en/guide/faq/) - Having problems?
