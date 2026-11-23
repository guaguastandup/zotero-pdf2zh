# Translation Environment Install & Update

Since **v4.1.0**, Zotero PDF2zh keeps **Server/plugin source updates** separate from **Python translation environment updates**. The current release installs packages **in the existing conda/uv environment**. It no longer creates staging or backup environments.

::: tip Current update flow
- Existing environments: install with `pip` / `uv pip` inside `zotero-pdf2zh-next-venv`.
- Windows Conda first looks for `<env>\\python.exe`, then asks conda itself via `conda run -n ... python`.
- Leftover `*-staging` / `*-backup` environments are removed during update. Translation uses only the canonical environment.
- Managed runtimes do not inherit system `PYTHONPATH` / `PYTHONHOME`; proxy, CUDA, PATH, and other unrelated settings are preserved.
- If a critical native dependency such as `pydantic_core` is damaged or resolves from global Python, the updater reinstalls the complete dependency set instead of running a mixed environment.
:::

## New users

New users do not need to choose BabelDOC, PyMuPDF, or a specific `pdf2zh_next` version manually.

On first actual use of `pdf2zh_next`, the Server:

1. keeps an existing uv/conda environment, or creates the canonical one (uv preferred for a fresh install);
2. probes PyPI, USTC, TUNA, Aliyun, and an optional custom index;
3. installs `pdf2zh_next==2.10.2`, `BabelDOC==0.7.1`, `PyMuPDF==1.28.2`, and their dependencies in that environment;
4. validates dependency completeness and the CLI entry point;
5. verifies DeepSeek V4 capability from the installed distribution without launching `pdf2zh_next --help`.

These three key dependencies are pinned to the current test baseline. Future Zotero PDF2zh releases can validate and adjust these pins; other transitive dependencies still resolve according to upstream metadata.

The Server itself can still start if installation fails. Retry later with `python update_packages.py`.

## Existing users

When an existing `pdf2zh_next` environment does not match the baseline, interactive startup asks once per Server version and dependency baseline:

```text
Existing Python translation environment detected
Current pdf2zh_next: ...

[Y] Check and update (recommended)
[N] Keep current environment

Choose [Y/n]:
```

Pressing Enter selects `Y`. The update installs into the current environment and may downgrade newer packages to the baseline. The version check skips the prompt only when all three key packages match. Non-interactive startup and the standalone Windows executable do not show this prompt.

If the user selects `N`, the same Server version and dependency baseline do not repeatedly ask. Retry later with:

```shell
python update_packages.py
```

## One-command manual update

From the `server` directory:

```shell
python update_packages.py
```

It keeps an existing uv or conda environment; a fresh install prefers uv. The configuration shipped with the Server specifies the BabelDOC version, so users do not need to choose it separately.

This command maintains the translation environment. Crop-compare uses PyMuPDF from the Python environment running the Server. Update that environment with `python -m pip install -r requirements.txt`, or start with `uv run --python 3.12 --with-requirements requirements.txt server.py`. The separate legacy `pdf2zh==1.9.11` environment retains its `PyMuPDF<1.25.3` constraint.

The flow is:

```text
find or create the canonical environment
    ↓
network + dependency checks
    ↓
install in the current environment
    ↓
validate CLI / critical native dependencies
```

The same command also repairs an existing damaged environment. Global Python paths are isolated first; a failed critical import triggers one complete reinstall. Healthy environments are not reinstalled.

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

## Dedicated Wenyi environment

Finish tasks and stop the Server, then install or repair the separate
`zotero-wenyi-venv` environment from the `server` directory:

```shell
python update_packages.py --engine wenyi
python manage_packages.py status --engine wenyi
```

Omitting `--engine` still updates only `pdf2zh_next`; `--engine all` now includes
Wenyi.

First use and explicit Wenyi updates install the latest stable `wenyi-cli`,
`wenyi-core` and `wenyi-babeldoc-bridge` available for the environment's Python
and dependency requirements from PyPI or the selected mirror. Both the resolver
preflight and installation use `--upgrade`, including when repairing an environment.
No GitHub version lookup or plugin PR is needed for each new package release.

Normal use reuses an installed environment when its declared packages are present,
without checking for or installing updates. The package manager resolves dependencies;
the Server does not add Wenyi runtime imports, entry-point probes or PDF2zh-specific
checks such as `bitstring`. Startup failures are reported by the CLI/bridge when used.
Existing managed configuration pins are removed during Server configuration migration,
while user-added packages are preserved. Manually configured external CLI/bridge
installations are not changed automatically.

Mirrors can lag behind PyPI. To prefer the official index:

```shell
python update_packages.py --engine wenyi --index-url https://pypi.org/simple
```

Restart after maintenance. See [Wenyi setup](./configuration.md#wenyi-engine-first-version).

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

### Diagnose the translation environment (read-only)

```shell
python manage_packages.py doctor
```

This command does not install packages, change the environment, or call a model API.
It reports the Server version, discovered uv/conda Python interpreters (both
when auto mode finds two environments), installed
dependency versions (including bitstring), and whether `bitstring.BitStream`
can be imported and constructed. Check the Server version before running
`python update_packages.py` to repair an incompatible environment. Review
local file paths before sharing diagnostic output.

### Update

```shell
python manage_packages.py update
```

Same as `python update_packages.py`: install into the current environment.

## What “latest” means

The updater never uses `--no-deps` to bypass upstream dependency constraints.

“Update” therefore means:

> **install the fixed test combination supplied by the current Zotero PDF2zh release while respecting upstream dependency constraints.**

The current baseline is `pdf2zh_next 2.10.2 + BabelDOC 0.7.1 + PyMuPDF 1.28.2`. BabelDOC 0.7.1 requires `PyMuPDF>=1.26.7,<2`, so PyMuPDF is not independently upgraded to 2.x. This is not a complete dependency lock file; the package manager still resolves other transitive dependencies.

## DeepSeek V4 thinking controls

Explicit DeepSeek V4 controls require the actual `pdf2zh_next` runtime to support the settings that map to:

```text
--deepseek-thinking-mode
--deepseek-reasoning-effort
```

New environments use `pdf2zh_next==2.10.2`; the minimum version check for DeepSeek thinking controls remains 2.9.0. Capability detection reads the installed distribution's settings/CLI source statically instead of starting the heavyweight `pdf2zh_next --help` path.

Existing users who decline the environment update can continue using other capabilities supported by their old environment. New DeepSeek V4 configurations default to thinking disabled; saved choices are preserved. Both enabling and disabling thinking require a capable runtime (`pdf2zh_next >= 2.9.0`). Unsupported runtimes stop before an API call and show an update message, because omitting the control parameters uses the provider's default of enabled thinking.

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
