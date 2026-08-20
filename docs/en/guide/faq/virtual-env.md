# Virtual Environment

::: tip Coming Soon
English documentation is under construction. Please switch to Chinese for complete documentation: [虚拟环境问题](/zh/guide/faq/virtual-env).
:::

::: warning Windows Conda (v4.1.1)
Upgrade, then run `python update_packages.py --env-tool conda`. This release installs into the canonical Conda environment and uses `conda run` to locate Python. It no longer creates staging or backup environments.
:::

## Can I skip virtual environment management?

If you only use one engine (pdf2zh_next or pdf2zh) and have Python 3.12.0 globally, you can skip virtual environment management:

```shell
pip install pdf2zh_next
python server.py --enable_venv=False
```
