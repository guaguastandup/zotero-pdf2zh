# 翻译选项

在 Zotero 中选中论文条目或 PDF 附件，右键打开「PDF2zh」菜单。

v4.1.0 会识别附件当前状态，避免把已经处理过的 PDF 再次送入不兼容操作。

## PDF 状态

可以把常见流程理解为：

```text
origin
→ mono / dual(LR/TB)
→ mono-cut / dual-cut / compare / crop-compare
```

其中 `compare` 和 `crop-compare` 是终态结果；如果再次执行同一操作，插件会在上传前直接提示，不会生成重复附件。

## 翻译 PDF

**输入：** 原始 PDF / 论文条目。

根据插件设置生成 mono、dual 以及用户启用的附加输出。

对已经生成的 mono / dual / compare / crop-compare 再执行「翻译 PDF」会被拒绝；需要重新翻译时请回到原始附件。

## 裁剪 PDF（Crop）

**支持输入：**

- origin
- mono
- dual

输出通常为：

- `mono-cut`
- `dual-cut`

对于 `pdf2zh_next` 的 **LR dual（左右同页）**，v4.1.0 会先在内部规范化为适合裁剪的 TB/交替页结构，然后继续完成真正的 `dual-cut`。

因此：

```text
LR dual
→ 内部 LR→TB
→ 真正裁剪
→ dual-cut
```

不会再把「LR→TB」本身错误当作 Crop 的最终结果。

::: tip 适用场景
Crop 主要用于把双栏论文拆成更适合窄屏阅读的单栏结构。
:::

## 双语对照（Compare）

**支持输入：**

- origin
- dual

输出 `compare`。

如果输入是原文，Server 会先生成需要的 dual，再完成对照布局。

`compare` 是终态；对 `compare` 再执行 Compare 会直接提示选择原文或 dual。

## 双语对照（裁剪后拼接 / Crop-Compare）

**支持输入：**

- origin
- dual
- dual-cut

适合双栏论文：先规范化/裁剪成单栏，再生成双语对照结果。

对于 LR dual：

```text
LR dual
→ 内部 LR→TB
→ 真正 crop-compare
→ crop-compare
```

v4.1.0 不会再出现“第一次 Crop-Compare 只把左右布局变成交替页，却把文件命名成 crop-compare”的问题。

`crop-compare` 也是终态。再次执行 Crop-Compare 时，插件和 Server 都会拒绝该操作。

## LR 与 TB 是什么？

### LR / Side by Side

原文和译文在同一页左右排列。

### TB / Alternating Pages

原文页与译文页交替出现。

::: info 历史名称
旧界面曾把 TB 写成“Top & Bottom / 上下对照”。当前 `pdf2zh_next` / BabelDOC 中它实际表示 **Alternating Pages**，不是同页上下排列。
:::

## 什么时候应该回到原文？

如果您想：

- 改翻译模型；
- 改语言；
- 改 Thinking 设置；
- 重新生成不同布局；
- 对已经是 compare / crop-compare 的文件重新处理；

推荐直接选择原始 PDF 或原始 dual，而不是把后处理结果继续链式加工。

## 批量处理

可以多选多个条目或附件执行同一种操作。

v4.1.0 修复了批处理统计：单个文件失败会计入 `failed`，不会再因为内部异常被吞掉而错误显示为成功；每次批处理完成后事件监听器也会释放。

## 操作选择建议

| 需求 | 推荐 |
|---|---|
| 普通翻译 | 翻译 PDF |
| 小屏/手机单栏阅读 | Crop |
| 原译文对照 | Compare |
| 双栏论文裁剪后对照 | Crop-Compare |
| 已经生成终态但想重做 | 回到原文/dual 重新生成 |

## 相关文档

- [配置说明](/zh/guide/configuration)
- [安装指南](/zh/guide/installation)
- [翻译环境更新](/zh/guide/package-update)
