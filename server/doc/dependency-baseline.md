# Python 依赖测试基线

本轮以 Python 3.12 验证以下组合，固定关键版本以便复现问题：

| 环境 | 关键依赖 |
| --- | --- |
| Server / crop-compare | PyMuPDF 1.28.2（`server/requirements.txt`） |
| pdf2zh_next 翻译环境 | pdf2zh_next 2.10.2、BabelDOC 0.7.1、PyMuPDF 1.28.2 |
| pdf2zh 旧翻译环境 | 保留 pdf2zh 1.9.11，遵循其 PyMuPDF <1.25.3 约束 |

BabelDOC 0.7.1 要求 `PyMuPDF>=1.26.7,<2`。旧 pdf2zh 的约束不同，必须保持引擎环境隔离。其他传递依赖仍由包管理器解析；这不是完整的依赖锁文件。

## 更新行为

- 新环境或手动更新使用 `config/venv.json.example` 中的版本组合。
- Server 启动时迁移托管依赖约束，保留额外包、Python 版本和其他用户设置。
- 交互式启动会检查新引擎、BabelDOC 和 PyMuPDF 是否同时匹配基线。原来“2.9.0 以上一律跳过”的判定仅保留为 DeepSeek 思考控制最低版本判断。
- 更新仍需沿用现有启动确认流程。选择不更新不会安装任何包；同一 Server 版本与依赖基线组合不会重复询问。非交互式启动和 Windows 独立 exe 不自动执行此更新提示。
- 固定版本可能将更高版本调整回基线；实际安装前显示当前版本和目标组合。
- 裁剪算法保持不变。DeepSeek 思考开关的执行规则见 [extraData 说明](extraData.md)。

## 分别更新两个环境

在实际启动 Server 的 Python 环境中，从 `server` 目录运行：

```sh
python -m pip install -r requirements.txt
python -c "import sys, pymupdf; print(sys.executable); print(pymupdf.VersionBind)"
```

如果使用 uv 启动 Server，沿用以下方式即可按 requirements 准备依赖：

```sh
uv run --python 3.12 --with-requirements requirements.txt server.py
```

翻译环境单独查看和更新：

```sh
python manage_packages.py status --engine pdf2zh_next
python update_packages.py --engine pdf2zh_next
```

这两种操作作用于不同的 Python 环境；更新翻译引擎并不自动更新 Server 的裁剪库。

## 回归验证

在仓库根目录运行，确保 Python 中已安装 Server 依赖：

```sh
PYTHONPATH=server python -m unittest discover -s server/tests -p 'test_dependency_baseline.py'
PYTHONPATH=server python -m unittest discover -s server/tests -p 'test_crop_rendering.py'
```

依赖测试覆盖旧配置迁移、旧提示记录失效、拒绝更新、匹配基线时跳过安装和沿用 Conda。裁剪测试将双栏内容实际写入 PDF、裁剪、重新打开并渲染，检查第二页文字既可提取也可见。

这些测试不涉及真实翻译 API，也不能代替问题 PDF 在 Zotero 中的验证。用户反馈的“crop-compare 第二页不可见”仍需要原文件及中间 dual 文件确认原因。

### 本轮验证记录（2026-11-19）

- macOS / Python 3.12 临时隔离环境实际安装 135 个包，`uv pip check` 通过；三项关键版本与表中一致。
- 新增依赖迁移与更新提示测试 8 项、PDF 裁剪渲染测试 1 项，均通过。
- 新引擎的环境健康检查、DeepSeek 思考控制能力检测及启用/禁用参数生成通过；额外使用实际 2.10.2 引擎与模拟 API 客户端检查最终请求，覆盖默认关闭、显式关闭、开启 high/max。未调用真实翻译 API。
- Windows x86_64 和 Linux x86_64 / glibc 2.28 目标的 Python 3.12 依赖解析通过，尚未在这两个平台实际运行。glibc 2.17 目标无法匹配本轮 ONNX Runtime 安装包，不在已验证范围内。
- 旧引擎依赖可独立解析；插件现有 30 项测试及 TypeScript 类型检查通过，覆盖编辑器设置、旧模型迁移、附件协议及连接错误提示。
- 旧 `deepseek-chat` / `deepseek-reasoner` 配置统一迁移到 `deepseek-v4-flash`。未明确保存思考开关时统一关闭；保留明确保存的选择，不从废弃模型名推导开启思考。
- DeepSeek 测试已按现行协议修正，不再依赖删除的常量。Server 全量 37 项测试通过，无跳过项。运行时无法明确传递开关时停止并提示更新；关闭思考时清理旧强度字段。
- CI 中 8 段 Python 检查已在本机执行通过。修正了依赖源码换行格式的 Server 启动断言，以及已不适用于回调/轮询进度流程的旧监听器清理断言。
- 已生成并核对 `plugin/build/zotero-pdf-2-zh.xpi`。本机脚手架 CLI 的更新提醒因缓存目录写权限失败，随后通过同一脚手架的 `Build` API 完成构建；未安装或发布此测试包。
- 连接提示已接入翻译、设置页测试连接及附件下载；批量提交前检查 Server，连续三次状态查询连接失败后显示已提交任务的恢复提示。模拟 Zotero 的流程测试验证了未启动 Server 时仅弹窗一次、不读取 PDF 内容、不提交翻译，以及临时断线恢复后不重复提交。尚未在真实 Zotero 窗口中人工验收这些提示。
- 自动化验证尚不能替代真实 PDF 翻译及 Zotero 内的人工验证，尤其是本次尚未拿到文件的不可见文字反馈。
