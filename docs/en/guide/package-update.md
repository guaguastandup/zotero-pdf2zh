# Package Update

Zotero PDF2zh treats **Server/plugin source updates** and **Python translation environment updates** as separate operations.

## Default policy: do not auto-upgrade the translation stack

Normal startup:

```shell
python server.py
```

does not proactively upgrade an existing `pdf2zh` / `pdf2zh_next` environment just to follow the newest release. If the current environment already satisfies the Server's declared baseline requirements, it is kept as-is.

This avoids unexpected parser, layout, or dependency regressions when upstream `pdf2zh_next`, BabelDOC, PyMuPDF, or related packages change.

> `server.py --check_update=True` checks the **Zotero PDF2zh Server source version**. It does not upgrade the Python translation packages.

## Check package-download connectivity first

Some users can browse normally but still cannot reliably reach PyPI or the host that serves the actual Python distribution files. Before updating, run:

```shell
python manage_packages.py network
```

This command is read-only. It probes in parallel:

- official PyPI
- USTC PyPI mirror
- TUNA PyPI mirror
- Aliyun PyPI mirror

The probe targets the `pdf2zh-next` project page and also reads a small prefix of one distribution file. This checks both package metadata and the actual artifact-download path instead of only testing a mirror homepage.

Example:

```text
🌐 Python package download preflight
  ❌ PyPI   https://pypi.org/simple (...)
  ✅ USTC   https://mirrors.ustc.edu.cn/pypi/simple (index 120 ms, artifact 85 ms)
  ✅ TUNA   https://pypi.tuna.tsinghua.edu.cn/simple (index 180 ms, artifact 130 ms)
  ✅ Aliyun https://mirrors.aliyun.com/pypi/simple (index 210 ms, artifact 160 ms)
  → recommended: USTC https://mirrors.ustc.edu.cn/pypi/simple
```

If every source fails and `HTTP_PROXY`, `HTTPS_PROXY`, or `ALL_PROXY` is configured, the diagnostic also points out that a stale proxy may be responsible. Proxy credentials and tokens are never printed; only the host/port is shown.

You can provide a preferred custom mirror:

```shell
python manage_packages.py network \
  --index-url "https://your-mirror.example/simple"
```

A working custom source is preferred. If it is unavailable, the built-in fallback sources are still tested.

## Inspect the current environment

From the `server` directory:

```shell
python manage_packages.py status
```

The default target is `pdf2zh_next`. The command prints versions such as:

```text
pdf2zh-next    2.9.0
BabelDOC       0.6.2
PyMuPDF        1.25.2
pypdf          6.16.1
```

Other targets:

```shell
python manage_packages.py status --engine pdf2zh
python manage_packages.py status --engine all
```

`status` is read-only and does not install, remove, or upgrade packages.

## Explicitly update to the newest compatible stack

Only run an update when you intentionally want to change the environment:

```shell
python manage_packages.py update
```

By default this updates only the `pdf2zh_next` environment. The update flow now:

1. prints the current environment versions;
2. probes PyPI, USTC, TUNA, Aliyun, and an optional custom source in parallel;
3. verifies that an actual distribution file can be reached;
4. runs the package manager's **dry-run dependency resolution** against usable sources without modifying the environment;
5. asks for confirmation only after both network and resolver checks pass;
6. if the preferred source fails during the real download, automatically retries other sources that passed preflight.

If no download path can be verified, the update stops before the install step and leaves the existing environment in place.

To maintain both translation environments:

```shell
python manage_packages.py update --engine all
```

The updater uses the package manager's normal dependency resolver and never uses `--no-deps`. Therefore "latest" means:

> **the newest compatible combination allowed by the current upstream dependency metadata.**

This is safer than forcing every component to its absolute newest version independently.

For scripted use:

```shell
python manage_packages.py update --yes
```

To prefer a specific package index:

```shell
python manage_packages.py update \
  --index-url "https://pypi.org/simple"
```

For very slow networks, increase the individual connectivity-probe timeout:

```shell
python manage_packages.py update --network-timeout 8
```

## DeepSeek V4 thinking controls

`deepseek_thinking_mode` / `deepseek_reasoning_effort` require `pdf2zh_next >= 2.9.0`.

Check first:

```shell
python manage_packages.py status
```

If the version is too old and you want the explicit DeepSeek V4 thinking controls, you can then choose to run:

```shell
python manage_packages.py update
```

The Server does not silently upgrade the whole translation environment in the background just to enable this feature.

## pdf2zh_next 2.9.0 / BabelDOC 0.6.x note

`pdf2zh_next 2.9.0` moved to the BabelDOC 0.6 parser line. Some PDFs with malformed xref/indirect-object structures that are still readable in normal PDF viewers can expose parser errors in this stack.

`manage_packages.py status` prints a warning for the known `pdf2zh-next >= 2.9.0 + BabelDOC <= 0.6.2` combination.

Do not use `--no-deps` to force a single component to a newer version. Upstream release bundles and Python package metadata can temporarily differ; prefer a combination that upstream declares compatible.

If only a small number of PDFs fail with errors such as `cannot parse object` or `Expected dict-like object, got NoneType`, first try re-downloading the original PDF or repacking that individual file. Zotero PDF2zh does not rewrite every user PDF by default.

## Keep the current environment unchanged

Do nothing. Continue to run:

```shell
python server.py
```

and the existing translation stack remains in place.

## Server source update channel

The Server source update channel remains controlled separately:

```shell
python server.py --update_source=github
python server.py --update_source=gitee
```

This is independent from Python package maintenance through `manage_packages.py`.
