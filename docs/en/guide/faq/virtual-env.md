# Virtual Environment

::: tip Coming Soon
English documentation is under construction. Please switch to Chinese for complete documentation: [虚拟环境问题](/zh/guide/faq/virtual-env).
:::

::: warning Windows Conda (v4.1.1)
Upgrade to v4.1.1 before starting the Server. v4.1.0 looked for Conda Python at `<env>\\Scripts\\python.exe`. The correct path is `<env>\\python.exe`. If a staging update fails and the old environment is still healthy, translation keeps using it.

Do not run `pip install --upgrade pdf2zh_next babeldoc` in the live environment. Use `python update_packages.py` instead.
:::

## Can I skip virtual environment management?

If you only use one engine (pdf2zh_next or pdf2zh) and have Python 3.12.0 globally, you can skip virtual environment management:

```shell
pip install pdf2zh_next
python server.py --enable_venv=False
```
