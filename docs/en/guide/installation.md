# Installation Guide

This guide will walk you through the installation and configuration of the Zotero PDF2zh plugin.

::: tip Before You Begin
Make sure you have installed:
- **Python 3.12.0** - [Download](https://www.python.org/downloads/)
- **Zotero 7** or **Zotero 8** - [Download](https://www.zotero.org/download/)
:::

---

## Step 0: Open Terminal

All subsequent commands need to be executed in a terminal.

### Windows Users

1. Press `Win + R`, type `cmd`, and press Enter
2. Or search for "cmd" or "Command Prompt" in the Start menu
3. ⚠️ **Run as Administrator**: Right-click "Command Prompt" and select "Run as administrator"

::: warning Windows Users
Do not create the project folder on the C drive (system drive). It is recommended to operate on the D drive or another non-system drive. For example: first execute `D:` to switch to the D drive, then execute subsequent commands.
:::

### macOS Users

1. Press `Cmd + Space`, type "Terminal" or "终端", and press Enter
2. Or go to "Applications" → "Utilities" → "Terminal"

### Linux Users

Open terminal (usually shortcut `Ctrl + Alt + T`)

---

## Choose Installation Method

- **[Method 1: uv Installation (Recommended)](#method-1-uv-installation-recommended)** - Fast and lightweight
- **[Method 2: conda Installation](#method-2-conda-installation)** - Mature and stable
- **[Method 3: Without Virtual Environment](#method-3-without-virtual-environment)** - Simple and direct
- **[Other Deployment Methods](#other-deployment-methods)** - Docker, Homebrew, Windows exe

---

## Method 1: uv Installation (Recommended)

### Step 1: Install uv

```shell
# macOS/Linux
wget -qO- https://astral.sh/uv/install.sh | sh

# Windows (in PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Step 2: Verify uv Installation

```shell
uv --version
```

If a version number is displayed, uv installation is complete.

::: warning Installation Failed
If `uv --version` check fails, you need to add the uv path to PATH and restart the terminal:

```shell
# macOS/Linux
export PATH="$HOME/.local/bin:$PATH"

# Windows PowerShell
$env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
```
:::

### Step 3: Download and Extract server

```shell
# Create and enter project folder
mkdir zotero-pdf2zh && cd zotero-pdf2zh

# Download and extract server folder
# macOS/Linux
wget https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/server.zip
unzip server.zip

# Windows
curl -L -o server.zip https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/server.zip
tar -xf server.zip

# Enter server folder
cd server
```

::: tip Download Failed?
If server.zip download fails, you can directly visit [server.zip](https://github.com/guaguastandup/zotero-pdf2zh/blob/main/server.zip) to download manually.
:::

### Step 4: Install Dependencies and Start

```shell
# Install dependencies
pip install -r requirements.txt

# Start service (using uv, default option)
python server.py
```

::: danger Important
The translation function depends on the Python script, **you need to keep the script running**. As long as you need to use the translation function, **do not close this Python script window**. Closing the script will disable the translation function.
:::

---

## Method 2: conda Installation

### Step 1: Install conda

Refer to the official documentation: [Miniconda Installation Guide](https://www.anaconda.com/docs/getting-started/miniconda/install#windows-command-prompt)

### Step 2: Verify conda Installation

```shell
conda --version
```

If a version number is displayed, conda installation is complete.

### Step 3: Download and Extract server

Same as [uv Installation - Step 3](#step-3-download-and-extract-server)

### Step 4: Install Dependencies and Start

```shell
# Install dependencies
pip install -r requirements.txt

# Start service (specify using conda)
python server.py --env_tool=conda
```

---

## Method 3: Without Virtual Environment

If you only use one of the pdf2zh_next/pdf2zh engines and your global Python version is 3.12.0, you can skip virtual environment management.

```shell
# 1. Create and enter project folder
mkdir zotero-pdf2zh && cd zotero-pdf2zh

# 2. Download and extract server folder
wget https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/refs/heads/main/server.zip
unzip server.zip

# 3. Enter server folder
cd server

# 4. Install packages
pip install -r requirements.txt
# If only using pdf2zh:
pip install pdf2zh==1.9.11 numpy==2.2.0
# If only using pdf2zh_next:
pip install pdf2zh_next

# 5. Run script (disable virtual environment management)
python server.py --enable_venv=False
```

---

## Install Zotero Plugin

1. Download the latest plugin: [v4.0.0](https://github.com/guaguastandup/zotero-pdf2zh/releases/download/v4.0.0/zotero-pdf-2-zh.xpi)

2. Open "Tools → Add-ons" in Zotero

3. Drag the downloaded xpi file into the add-ons window to install

4. If the feature doesn't work, please restart Zotero

::: tip Auto Update
You can check for updates in Zotero or enable auto-update to get the latest plugin version.
:::

---

## Configure Plugin

1. Open "Tools → PDF2zh Preferences"

2. Configure the following options:
   - **Python Server IP**: Default is `http://127.0.0.1:8890`
   - **Translation Engine**: Select `pdf2zh` or `pdf2zh_next`
   - **LLM API**: Configure translation service (see [Configuration](/en/guide/configuration))

3. Click the "Check Connection" button to verify the service is running properly

---

## Default Configuration

Default options when executing `python server.py`:

| Configuration | Default | Description |
|---------------|---------|-------------|
| Virtual Environment Management | On | Using `uv` |
| Auto Install Dependencies | On | Auto install on first run |
| Auto Check Updates | On | Check on startup |
| Update Source | gitee | Friendly for users in China |
| Port | 8890 | Service port |
| Mirror Source | USTC | Speed up package installation |

---

## Command Line Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--enable_venv` | `True` | Enable virtual environment management |
| `--env_tool` | `uv` | Virtual environment tool (uv/conda) |
| `--port` | `8890` | Service port |
| `--check_update` | `True` | Auto check for updates |
| `--update_source` | `gitee` | Update source (github/gitee) |
| `--enable_mirror` | `True` | Enable mirror |
| `--mirror_source` | USTC mirror | Mirror source address |

### Common Examples

```shell
# Change port
python server.py --port=9999

# Use conda
python server.py --env_tool=conda

# Disable auto check for updates
python server.py --check_update=False

# Switch update source
python server.py --update_source="github"

# Disable mirror
python server.py --enable_mirror=False
```

---

## Other Deployment Methods

| Method | Description | Use Case |
|--------|-------------|----------|
| **[Docker](/en/guide/docker)** | Environment isolation | Server deployment, multi-environment management |
| **[Homebrew](/en/guide/homebrew)** | Automated management | macOS/Linux users |
| **Windows exe** | No environment setup | Windows users who don't want to configure Python |

---

## Important Notes

- If using the uv installation method, **do not move the server folder or rename it** after installation
- If update check fails on startup, you can switch the update source based on network conditions

---

## Next Steps

- [Configuration](/en/guide/configuration) - Plugin and service configuration
- [Translation Options](/en/guide/translation-options) - Various translation features
- [FAQ](/en/guide/faq/) - Having problems?
