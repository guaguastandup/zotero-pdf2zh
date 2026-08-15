# Package Update

Zotero PDF2zh treats **Server/plugin source updates** and **Python translation environment updates** as separate operations.

## Normal users: one command

From the `server` directory, run:

```shell
python update_packages.py
```

That is the complete user-facing package update command. Users do not need to choose PyPI mirrors or understand BabelDOC/PyMuPDF dependency details.

Internally it automatically:

1. finds the current `pdf2zh_next` environment;
2. probes PyPI, USTC, TUNA, Aliyun, and optional custom sources;
3. verifies that an actual distribution file can be downloaded;
4. chooses a usable fast source;
5. performs dependency resolution preflight without modifying the environment;
6. installs only versions allowed by the current dependency constraints;
7. falls back to another validated source if the preferred source fails;
8. stops safely and keeps the existing environment if no safe update path is available.

Running `update_packages.py` is itself the user's explicit choice to update, so it does not ask for a second `y/N` confirmation.

::: tip No background package upgrades
Normal startup:

```shell
python server.py
```

does not proactively upgrade an existing `pdf2zh` / `pdf2zh_next` environment. Python translation packages change only when the user explicitly runs `python update_packages.py`.
:::

## Advanced diagnostics

Normal users do not need the commands below. Use `manage_packages.py` only when diagnosing problems.

### Check package-download connectivity

```shell
python manage_packages.py network
```

This command is read-only. It probes:

- official PyPI
- USTC PyPI mirror
- TUNA PyPI mirror
- Aliyun PyPI mirror

The probe targets the `pdf2zh-next` project and reads a small prefix of an actual distribution file, so it verifies the real package-download path rather than only testing a mirror homepage.

If all sources fail while `HTTP_PROXY`, `HTTPS_PROXY`, or `ALL_PROXY` is configured, diagnostics point out that a stale proxy may be responsible without printing proxy credentials or tokens.

### Inspect installed versions

```shell
python manage_packages.py status
```

Example:

```text
pdf2zh-next    2.9.0
BabelDOC       0.6.2
PyMuPDF        1.25.2
pypdf          6.16.1
```

### Custom mirror or timeout

```shell
python update_packages.py \
  --index-url "https://pypi.org/simple"

python update_packages.py --network-timeout 8
```

## Update policy

The updater uses normal uv/pip dependency resolution and never uses `--no-deps` to bypass upstream constraints. Therefore "update to latest" means:

> **update to the newest compatible combination allowed by the current upstream dependency metadata.**

If a newer individual component conflicts with the installed `pdf2zh_next` dependency constraints, the updater does not force an incompatible combination.

## DeepSeek V4 thinking controls

`deepseek_thinking_mode` / `deepseek_reasoning_effort` require `pdf2zh_next >= 2.9.0`. When an update is needed, normal users still run only:

```shell
python update_packages.py
```

The Server does not silently upgrade the environment in the background just to enable this feature.

## Special PDF parser failures

Some structurally malformed PDFs that still open in normal PDF viewers can expose xref/indirect-object parser failures in particular BabelDOC versions.

If only a small number of PDFs fail with errors such as `cannot parse object` or `Expected dict-like object, got NoneType`, first try re-downloading the original PDF or repacking only that file. Zotero PDF2zh does not rewrite every user PDF by default.

## Keep the current environment unchanged

Do nothing. Continue to run:

```shell
python server.py
```

and the existing translation stack remains in place.

## Server source update channel

Server source updates remain separate:

```shell
python server.py --update_source=github
python server.py --update_source=gitee
```

This is independent from Python package updates through `update_packages.py`.
