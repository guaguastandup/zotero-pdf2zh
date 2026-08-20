# Translation Environment Install & Update

Since **v4.1.0**, Zotero PDF2zh keeps **Server/plugin source updates** separate from **Python translation environment updates**. The current release installs packages **in the existing conda/uv environment**. It no longer creates staging or backup environments.

::: tip Current update flow
- Existing environments: install with `pip` / `uv pip` inside `zotero-pdf2zh-next-venv`.
- Windows Conda first looks for `<env>\\python.exe`, then asks conda itself via `conda run -n ... python`.
- Leftover `*-staging` / `*-backup` environments are removed during update. Translation uses only the canonical environment.
:::

## New users

New users do not need to choose BabelDOC, PyMuPDF, or a specific `pdf2zh_next` version manually.

On first actual use of `pdf2zh_next`, the Server:

1. keeps an existing uv/conda environment, or creates the canonical one (uv preferred for a fresh install);
2. probes PyPI, USTC, TUNA, Aliyun, and an optional custom index;
3. installs `pdf2zh_next >= 2.9.0,<3.0.0` and its dependencies in that environment;
4. validates dependency completeness and the CLI entry point;
5. verifies DeepSeek V4 capability from the installed distribution without launching `pdf2zh_next --help`.

The upper bound is intentional. If upstream later releases `pdf2zh_next 3.x`, a later Zotero PDF2zh release must validate and widen the supported range.

The Server itself can still start if installation fails. Retry later with `python update_packages.py`.

## Existing users

When an existing `pdf2zh_next` environment is detected, the current Server version asks once:

```text
Existing Python translation environment detected
Current pdf2zh_next: ...

[Y] Check and update (recommended)
[N] Keep current environment

Choose [Y/n]:
```

Pressing Enter selects `Y`. The update installs into the current environment. If `pdf2zh_next` is already **2.9.0 or newer**, the startup prompt is skipped.

If the user selects `N`, the same Server version does not repeatedly ask. Retry later with:

```shell
python update_packages.py
```

## One-command manual update

From the `server` directory:

```shell
python update_packages.py
```

This is the only maintenance command normal users need. It keeps an existing uv or conda environment; a fresh install prefers uv. BabelDOC is a dependency of `pdf2zh_next` and does not need a separate version pin.

The flow is:

```text
find or create the canonical environment
    ↓
network + dependency checks
    ↓
install in the current environment
    ↓
validate CLI / dependencies
```

### Custom index or timeout

```shell
python update_packages.py \
  --index-url "https://pypi.org/simple"

python update_packages.py --network-timeout 8
```

To force one environment manager explicitly:

```shell
python update_packages.py --env-tool uv
python update_packages.py --env-tool conda
```

## Advanced diagnostics

### Check package-download connectivity

```shell
python manage_packages.py network
```

This is read-only. It probes official PyPI, USTC, TUNA, and Aliyun and reads a small prefix of a real distribution artifact rather than only testing a mirror homepage.

### Inspect installed versions

```shell
python manage_packages.py status
```

### Update

```shell
python manage_packages.py update
```

Same as `python update_packages.py`: install into the current environment.

## What “latest” means

The updater never uses `--no-deps` to bypass upstream dependency constraints.

“Update” therefore means:

> **install the newest compatible combination allowed by both the Zotero PDF2zh supported range and current upstream dependency metadata.**

For v4.1.0, the managed `pdf2zh_next` range is `>=2.9.0,<3.0.0`. It does not guarantee that every individual BabelDOC or PyMuPDF package reaches its independently newest release if that combination is not allowed by the upstream dependency graph.

## DeepSeek V4 thinking controls

Explicit DeepSeek V4 controls require the actual `pdf2zh_next` runtime to support the settings that map to:

```text
--deepseek-thinking-mode
--deepseek-reasoning-effort
```

v4.1.0 requires `pdf2zh_next >=2.9.0,<3.0.0` for new environments. Capability detection reads the installed distribution's settings/CLI source statically instead of starting the heavyweight `pdf2zh_next --help` path.

Existing users who decline the environment update can continue using capabilities supported by their old environment. DeepSeek V4 **defaults to no thinking**, so an older runtime is still allowed to translate. The Server only requires `pdf2zh_next >= 2.9.0` when the user explicitly enables thinking; otherwise it blocks that request before any API call so the setting cannot be silently ignored.

## Configuration migration

v4.1.0 no longer overwrites existing `config.json`, `config.toml`, or `venv.json` from their `.example` templates on every startup.

During migration it:

- preserves existing user values;
- preserves unknown custom keys and translators;
- adds missing defaults for normal configuration fields;
- refreshes release-managed package constraints in `venv.json` while preserving additional third-party packages added by the user;
- backs up an unparseable old config as `.invalid.bak` before restoring defaults.

## Special PDF parser failures

Some malformed PDFs can still trigger BabelDOC/PyMuPDF parser errors such as:

```text
cannot parse object
Expected dict-like object, got NoneType
```

Zotero PDF2zh does not automatically rewrite, repack, or rasterize every user PDF. For isolated failures, re-download the original PDF first and only repair the affected file if necessary.

## Server source updates

Server source updates remain separate:

```shell
python server.py --update_source=github
python server.py --update_source=gitee
```

Both GitHub and Gitee are tried for version checks and `server.zip` downloads. `--update_source` only chooses **which source is tried first**; if it fails or is older, the other source is used. The unpacked Server version is still verified.

Gitee Release attachments may show a security captcha or 404, so the updater also tries Gitee `raw/vX.Y.Z/server.zip`, GitHub Releases, and the versioned file in the GitHub repo. Do not use Gitee source archives (`repository/archive/*.zip`); that endpoint often returns HTML.

Manual download:

```text
https://github.com/guaguastandup/zotero-pdf2zh/releases/latest/download/server.zip
https://gitee.com/guaguastandup/zotero-pdf2zh/raw/v4.1.1/server.zip
```

Source updates and Python translation-environment updates remain independent operations.

## Project notices

On startup the Server fetches `server/notice.json` from `main`. `community` (QQ groups, join answer, docs) is always shown; `notices` are filtered by the local version. Fetch failures are ignored and never block startup.

To change the QQ group number, retire an announcement, or warn that a version cannot auto-update, edit that file on `main`. No new Server release is required.

Empty `affects` or `*` shows the notice to every version. Set `enabled` to `false` to retire a notice. Groups with `status: full` are not printed.
