# Translation Environment Install & Update

Zotero PDF2zh v4.1.0 keeps **Server/plugin source updates** separate from **Python translation environment updates**, and now protects Python installs with a staging-and-rollback workflow.

## New users

New users do not need to choose BabelDOC, PyMuPDF, or a specific `pdf2zh_next` version manually.

On first actual use of `pdf2zh_next`, the Server:

1. creates an isolated staging environment;
2. probes PyPI, USTC, TUNA, Aliyun, and an optional custom index;
3. verifies access to a real distribution artifact;
4. lets uv/pip resolve the complete dependency set;
5. installs the newest compatible `pdf2zh_next` within v4.1.0's supported `>=2.9.0,<3.0.0` range together with its compatible dependencies;
6. validates dependency completeness and the `pdf2zh_next --help` runtime;
7. additionally verifies DeepSeek V4 thinking flags for `pdf2zh_next`;
8. switches the staging environment into place only after every check succeeds.

The upper bound is intentional. If upstream later releases `pdf2zh_next 3.x`, an already released Zotero PDF2zh v4.1.0 will not silently cross a potentially breaking major version; a later Zotero PDF2zh release must validate and widen the supported range.

If installation fails, the Server does not leave a half-installed environment that is later treated as valid. The Server itself can still start and installation can be retried later.

## Existing users upgrading to v4.1.0

When an existing `pdf2zh_next` environment is detected, the current Server version asks once whether to perform a safe environment refresh:

```text
Existing Python translation environment detected
Current pdf2zh_next: ...

[Y] Safely check and update (recommended)
[N] Keep current environment

Choose [Y/n]:
```

Pressing Enter selects `Y`.

Selecting update does **not** run an in-place upgrade inside the currently working environment. A new staging environment is installed and validated first.

Therefore:

- success: the new environment becomes active and the previous environment is kept as a backup;
- download failure: the old environment is not modified;
- dependency-resolution failure: the old environment is not modified;
- staging installation failure: the old environment is not modified;
- runtime validation failure: the old environment is not modified;
- switch failure: the Server attempts to restore the previous environment.

If the update fails, the Server continues with the previous environment. Features that require a newer runtime fail safely when they are actually used.

If the user selects `N`, the same Server version does not repeatedly ask. If the user selected update but that attempt failed, the same Server version also does not keep prompting on every launch; `python update_packages.py` remains available for a manual retry.

## One-command manual update

From the `server` directory:

```shell
python update_packages.py
```

This uses the same transaction as the startup prompt:

```text
staging environment
    ↓
network + dependency checks
    ↓
install
    ↓
runtime validation
    ↓
switch only on success
```

Users do not need to manage BabelDOC, PyMuPDF, pypdf, or other transitive dependencies themselves.

### Custom index or timeout

```shell
python update_packages.py \
  --index-url "https://pypi.org/simple"

python update_packages.py --network-timeout 8
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

### Advanced safe update

```shell
python manage_packages.py update
```

The advanced update command now uses the same staging transaction; there is no separate in-place upgrade path.

## What “latest” means

The updater never uses `--no-deps` to bypass upstream dependency constraints.

“Update” therefore means:

> **install the newest compatible combination allowed by both the Zotero PDF2zh supported range and current upstream dependency metadata.**

For v4.1.0, the managed `pdf2zh_next` range is `>=2.9.0,<3.0.0`. It does not guarantee that every individual BabelDOC or PyMuPDF package reaches its independently newest release if that combination is not allowed by the upstream dependency graph.

## DeepSeek V4 thinking controls

Explicit DeepSeek V4 controls require the actual `pdf2zh_next` runtime to expose:

```text
--deepseek-thinking-mode
--deepseek-reasoning-effort
```

v4.1.0 requires `pdf2zh_next >=2.9.0,<3.0.0` for new environments and also performs a direct runtime capability check instead of trusting only a version string.

Existing users who decline the environment update can continue using capabilities supported by their old environment. If they later use DeepSeek V4 with an unsupported runtime, the Server blocks the request before any translation API call so the thinking setting cannot be silently ignored and generate unexpected reasoning cost.

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

Source updates and Python translation-environment updates are independent operations.
