from pathlib import Path
import json

readme_path = Path('README.md')
text = readme_path.read_text(encoding='utf-8')
old_intro = '在Zotero中使用[PDF2zh](https://github.com/Byaidu/PDFMathTranslate)和[PDF2zh_next](https://github.com/PDFMathTranslate/PDFMathTranslate-next)'
new_intro = '在 Zotero 中直接使用 [PDF2zh](https://github.com/Byaidu/PDFMathTranslate) 与 [PDF2zh_next](https://github.com/PDFMathTranslate/PDFMathTranslate-next) 翻译 PDF，保留公式与排版，并提供双语对照、裁剪阅读、批量翻译与多种 LLM 服务配置。'
if old_intro not in text:
    raise SystemExit('README intro marker not found')
text = text.replace(old_intro, new_intro, 1)

old_notice = '> 📢: 桌面端构建中(Coming Soon!)，改动较大，有新的功能&修复了旧bug，暂不接收新的Pull Request'
new_notice = '''> 🚀 **v4.1.0**：支持 DeepSeek V4 Thinking 控制；翻译环境会自动识别已有 uv/conda，新环境优先使用 uv，并通过 staging + rollback 安全安装/更新；完善 LR/TB Dual、Crop / Compare / Crop-Compare 状态处理；配置迁移不再覆盖用户已有设置；Server 默认仅监听本机地址。\n>\n> 📦 **下载最新版本：** [Zotero 插件 XPI](https://github.com/guaguastandup/zotero-pdf2zh/releases/latest/download/zotero-pdf-2-zh.xpi) · [Server](https://github.com/guaguastandup/zotero-pdf2zh/releases/latest/download/server.zip) · [完整文档](https://zotero-pdf2zh.github.io/)'''
if old_notice not in text:
    raise SystemExit('README old coming-soon notice not found')
text = text.replace(old_notice, new_notice, 1)

# Make the manual maintenance entry explicit near the existing v4.1.0 upgrade note.
old_upgrade = '- 📢 **v4.1.0 升级提示**：已有 Server 用户首次启动本版本时，会询问是否安全更新 Python 翻译环境。DeepSeek V4 用户建议选择 `Y`；更新会先在 staging 环境验证，失败不会原地修改当前可用环境。新用户首次使用 `pdf2zh_next` 时会自动创建并验证兼容环境。'
new_upgrade = old_upgrade + '\n- 🔧 如果之前选择了 `N`、更新时网络失败，或希望主动维护环境，可在 `server` 目录运行 `python update_packages.py`。该命令会自动沿用已有 uv/conda；没有现有环境时优先 uv。'
if old_upgrade not in text:
    raise SystemExit('README v4.1 upgrade note not found')
text = text.replace(old_upgrade, new_upgrade, 1)
readme_path.write_text(text, encoding='utf-8')

package_path = Path('plugin/package.json')
package = json.loads(package_path.read_text(encoding='utf-8'))
package['description'] = 'PDF translation for Zotero with PDF2zh/PDF2zh_next, bilingual layouts, batch processing, and DeepSeek V4 support.'
package['config']['addonName'] = 'Zotero PDF2zh'
package_path.write_text(json.dumps(package, ensure_ascii=False, indent=4) + '\n', encoding='utf-8')

print('updated README and plugin package metadata')
