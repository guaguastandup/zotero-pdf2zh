# Installation Guide

This guide applies to Zotero PDF2zh **v4.1.1** (including v4.1.0 features). Starting with v4.1.0, the Server source, Zotero plugin, and Python translation environment are maintained separately. Normal users do not need to choose exact `pdf2zh_next`, BabelDOC, or PyMuPDF versions manually.

::: tip Before You Begin
Recommended:
- **Python 3.12**
- **Zotero 7 / 8 / 9 / 10**
- **uv** for new installations, or an existing conda setup
:::

::: warning Windows Conda users
Use **v4.1.1** or later. v4.1.0 looked for Conda Python at `<env>\\Scripts\\python.exe` and could treat a healthy environment as broken. The correct path is `<env>\\python.exe` at the environment root.
:::

## 1. Download the Server

Download `server.zip` from the latest GitHub Release. Do not use a static zip from the repository `main` branch:

```text
https://github.com/guaguastandup/zotero-pdf2zh/releases/latest/download/server.zip
```

After extracting, the layout should look like:

```text
zotero-pdf2zh/
└── server/
    ├── server.py
    ├── requirements.txt
    ├── update_packages.py
    ├── config/
    └── utils/
```

Enter the Server directory:

```shell
cd server
```

## 2. Install Server Runtime Dependencies

This installs only the dependencies required to run the Server itself, such as Flask, TOML and PDF utilities. You do **not** need to install `pdf2zh_next` or BabelDOC manually:

```shell
python -m pip install -r requirements.txt
```

## 3. Recommended: Install uv

If this machine does not already have a managed translation environment, install uv:

```shell
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows PowerShell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verify:

```shell
uv --version
```

Existing conda users do not need to migrate to uv. The default `env_tool=auto` keeps an existing uv or conda project environment; only a fresh installation prefers uv.

## 4. Start the Server

For normal use:

```shell
python server.py
```

Default address:

```text
http://127.0.0.1:8890
```

The Server binds to `127.0.0.1` by default. Only expose it to other devices when you intentionally need remote access:

```shell
python server.py --host 0.0.0.0
```

::: warning Remote access
`--host 0.0.0.0` exposes the Server to other devices reachable on the current network. Use it only when you understand the firewall/network implications.
:::

## 5. What Happens on the First Translation?

New users do not need to run `pip install pdf2zh_next` first.

On the first real `pdf2zh_next` translation, the Server automatically:

1. chooses the environment manager (uv for a fresh setup);
2. probes PyPI, USTC, TUNA, Aliyun and optional custom indexes;
3. creates a separate staging environment;
4. installs the newest compatible `pdf2zh_next` in the current supported range (`>=2.9.0,<3.0.0`) together with compatible dependencies;
5. validates dependencies and DeepSeek V4 capability;
6. switches the staging environment into place only after validation succeeds.

A failed install does not leave a half-installed environment that is later treated as valid.

## 6. Existing Users Upgrading to v4.1.0 / v4.1.1

If an existing uv or conda translation environment is found, the new Server asks once whether to perform a safe refresh:

```text
Existing Python translation environment detected
Current pdf2zh_next: ...

[Y] Safely check and update (recommended)
[N] Keep current environment

Choose [Y/n]:
```

Press Enter to select `Y`.

The update path is:

```text
staging install
→ validation
→ switch on success
→ keep the old environment on failure (v4.1.1: a healthy old environment still serves translations)
```

The currently working environment is never upgraded in place. Do not run `pip install --upgrade pdf2zh_next babeldoc` in the live environment. If you choose `N`, existing capabilities continue to work. Features that require a newer runtime, such as explicit DeepSeek V4 Thinking Control, fail safely before an API request if the old runtime does not support them.

To retry later:

```shell
python update_packages.py
```

This command automatically detects an existing uv or conda environment; if no managed environment exists, it prefers uv.

## 7. conda Users

If your previous installation already uses conda, simply run:

```shell
python server.py
```

The default `auto` mode discovers and keeps the existing conda environment.

To force conda only:

```shell
python server.py --env_tool=conda
python update_packages.py --env-tool conda
```

An explicitly selected manager is strict: conda failure does not silently switch to uv, and vice versa.

On Windows, Conda Python is `<conda>\\envs\\zotero-pdf2zh-next-venv\\python.exe`. uv / venv use `Scripts\\python.exe`. v4.1.1 distinguishes these paths.

## 8. Without a Managed Virtual Environment (Advanced)

Only use this when you intentionally maintain the Python environment yourself:

```shell
python server.py --enable_venv=False
```

The Server will not update your system Python environment in this mode. Runtime capability checks such as DeepSeek V4 protection still apply.

## 9. Install the Zotero Plugin

Latest XPI:

```text
https://github.com/guaguastandup/zotero-pdf2zh/releases/latest/download/zotero-pdf-2-zh.xpi
```

Steps:

1. Zotero → **Tools → Add-ons**;
2. drag the downloaded `.xpi` into the Add-ons window;
3. restart Zotero after installation;
4. open **Tools → PDF2zh Preferences**;
5. keep the Python Server URL at `http://127.0.0.1:8890` unless you intentionally changed it.

## 10. Default Server Arguments

| Parameter | Default | Description |
|---|---|---|
| `--host` | `127.0.0.1` | Localhost-only by default |
| `--port` | `8890` | Server port |
| `--enable_venv` | `True` | Enable managed translation environments |
| `--env_tool` | `auto` | Keep existing uv/conda; prefer uv for a fresh environment |
| `--check_update` | `True` | Check Server updates on startup |
| `--update_source` | `gitee` | Server update source; can be changed to github |
| `--enable_mirror` | `True` | Enable package-download source optimization |
| `--skip_install` | `False` | Disable automatic environment creation/repair |

Examples:

```shell
# Change port
python server.py --port 9999

# Force uv
python server.py --env_tool=uv

# Force conda
python server.py --env_tool=conda

# Use GitHub Release for Server update checks
python server.py --update_source=github

# Allow LAN access (advanced)
python server.py --host 0.0.0.0
```

## 11. Windows Standalone exe (Advanced)

A Windows standalone `pdf2zh_next` executable can also be used:

```shell
python server.py --enable_winexe=True --winexe_path="<path-to-pdf2zh.exe>"
```

The standalone executable must be maintained separately. DeepSeek V4 Thinking Control checks its capability before translation and will not silently ignore an unsupported setting.

## Notes

- Keep `server.py` running while translating.
- Do not use `--no-deps` to force incompatible BabelDOC / PyMuPDF / pdf2zh_next combinations.
- Prefer the startup update prompt or `python update_packages.py` for translation-environment maintenance.
- Some malformed PDFs may still trigger upstream BabelDOC / PyMuPDF parser failures; Zotero PDF2zh does not automatically rewrite or rasterize every user PDF.

## Next Steps

- [Configuration](/en/guide/configuration)
- [Translation Options](/en/guide/translation-options)
- [Extra Parameters](/en/guide/extra-params)
- [Translation Environment Updates](/en/guide/package-update)
- [FAQ](/en/guide/faq/)
