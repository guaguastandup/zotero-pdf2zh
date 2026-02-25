# 翻译选项

在 Zotero 中对条目或 PDF 右键，选择「PDF2zh」翻译选项进行翻译。

![右键菜单](https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/images/menu.png)

## 翻译选项说明

### 翻译 PDF (Translate PDF)

点击原文 PDF 或论文条目，生成在 Zotero 插件设置端所选择的默认翻译文件。

![翻译 PDF](https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/images/image3.png)

### 裁剪 PDF (Crop PDF)

选择 dual/mono 类型附件，将对选择的附件在宽度 1/2 处裁剪，然后上下拼接。此功能适合手机阅读。

![裁剪 PDF](https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/images/image4-1.png)

::: tip 注意事项
1. 本选项会将页面两侧空白处进行裁剪
2. 若产生截断原文内容的情况，可将 `server/utils/config.py` 中的 `config.pdf_w_offset` 值降低
:::

### 双语对照 (Compare PDF)

点击此选项，会生成左边为原文、右边为翻译后文本的 PDF。

![双语对照](https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/images/image4-3.png)

::: tip 选项说明
- 选择「Dual 文件翻译页在前」可以交换生成顺序
- 此选项等同于翻译引擎为 pdf2zh_next，且「双语(Dual)文件显示模式」为 **Left&Right** 时生成的文件
:::

### 双语对照(裁剪) (Crop-Compare PDF)

此选项仅针对**双栏 PDF 论文**。它会先将 PDF **竖向裁剪为单栏文件**，再左右拼接。

![双语对照(裁剪)](https://raw.githubusercontent.com/guaguastandup/zotero-pdf2zh/main/images/image4-2.png)

## 批量翻译

您可以多选条目，右键菜单，然后进行批量 PDF 翻译。

::: tip 批量翻译
1. 在 Zotero 中按住 Ctrl/Cmd 键多选条目
2. 右键选择「PDF2zh → 翻译 PDF」
3. 等待所有文件翻译完成
:::
