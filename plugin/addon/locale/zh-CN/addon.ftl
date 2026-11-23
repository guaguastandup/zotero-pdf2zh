startup-begin = 插件加载中
startup-finish = 插件已就绪

prefs-title = PDF2zh

prefs-menu-translate = 翻译PDF
prefs-menu-cut = 裁剪PDF
prefs-menu-compare = 双语对照
prefs-menu-crop-compare = 双语对照(裁剪后拼接)

operation-progress-title = PDF2zh
operation-progress-processing = 正在准备请求...
operation-progress-submitting = 正在提交「{ $fileName }」...
operation-progress-accepted = 已提交，正在{ $action }「{ $fileName }」
operation-progress-running = 正在{ $action }「{ $fileName }」{ $suffix }
operation-progress-importing = 服务器已完成，正在导入「{ $fileName }」的附件...
operation-progress-file-done = 「{ $fileName }」已导入
operation-progress-file-failed = 「{ $fileName }」失败：{ $message }
operation-progress-waiting = 等待处理「{ $fileName }」
operation-progress-reconnecting = 与 Server 的连接暂时中断，正在重新检查；任务可能仍在运行
operation-progress-summary = 正在处理 { $done }/{ $total } 个文件
operation-action-translate = 翻译
operation-action-crop = 裁剪
operation-action-compare = 生成双语对照
operation-action-crop-compare = 生成裁剪双语对照
operation-batch-progress = 第 { $current }/{ $total } 个：{ $text }
operation-error-translate = “翻译 PDF”只支持原始 PDF。请选择原文附件或论文条目。
operation-error-crop = 当前文件不能再次裁剪。请选择原文、mono 或 dual 附件。
operation-error-compare = 当前文件不能执行“双语对照”。请选择原文或 dual 附件。
operation-error-crop-compare = 当前文件不能执行“双语对照（裁剪）”。请选择原文、dual 或 dual-cut 附件。
operation-error-crop-compare-terminal = 该 PDF 已经是“双语对照（裁剪）”结果，无需再次处理。请选择原文或 dual 附件。
operation-error-compare-terminal = 该 PDF 已经是“双语对照”结果，无需再次处理。请选择原文或 dual 附件。

operation-error-no-selection = 请先选择一个条目或 PDF 附件。
operation-error-unknown = 未知错误
operation-error-prefix = 错误：{ $message }
operation-error-single-file = 处理文件 { $fileName } 失败：{ $message }
operation-batch-started = 已开始处理 { $count } 个文件，请稍候
operation-batch-completed =
    { $kind ->
        [failed] 处理失败。失败 { $failed } 个
        [mixed] 处理结束。成功 { $succeeded } 个，失败 { $failed } 个
       *[success] 全部完成。成功 { $succeeded } 个
    }
operation-error-no-files = 服务器未返回可导入的文件
operation-error-completed-no-files = 任务已完成，但 Server 未返回任何文件
operation-error-partial-attachments = 仅导入 { $attached }/{ $total } 个附件：{ $message }

server-error-missing-address-title = 还没有填写 PDF2zh Server 地址
server-error-missing-address-help = 请打开 Zotero 设置 → PDF2zh，在“Python Server IP”中填写 Server 窗口显示的完整地址，例如 http://localhost:8890，然后点击“测试连接”。
server-error-invalid-address-title = PDF2zh Server 地址格式不正确
server-error-invalid-address-help = 请打开 Zotero 设置 → PDF2zh，核对“Python Server IP”。地址需要包含 http:// 或 https://、主机和端口，例如 http://localhost:8890。请填写 Server 地址，不要填写模型服务的 API 地址或附带查询参数的网页地址。
server-error-unreachable-title = 暂时无法连接到 PDF2zh Server
server-error-unreachable-help =
    Server 可能还没有启动，或插件填写的地址、端口不正确。
    1. 先启动 PDF2zh Server，等待窗口显示服务已启动，并保持窗口打开。
    2. 打开 Zotero 设置 → PDF2zh，核对“Python Server IP”与 Server 窗口中的地址一致。
    3. 点击“测试连接”，连接成功后再操作。
    如果使用另一台电脑或远程 Server，请确认该电脑的服务和网络可用。
server-error-timeout-title = 连接 PDF2zh Server 超时
server-error-timeout-help = Server 没有及时响应。请确认 Server 窗口仍在运行，核对地址与端口；使用远程 Server 时也请检查网络。随后在 Zotero 设置 → PDF2zh 中点击“测试连接”。
server-error-unexpected-response-title = Server 地址或版本可能不匹配
server-error-unexpected-response-help = 这个地址返回了插件无法识别的内容。请核对“Python Server IP”，确认连接的是 PDF2zh Server，而不是模型 API 或其他网页。如果地址正确，请将插件和 Server 更新为配套版本。
server-error-access-denied-title = 当前地址拒绝了连接请求
server-error-access-denied-help = 请核对 PDF2zh Server 地址。如果使用远程或共享 Server，请检查访问权限，或联系该服务的提供者。
server-error-file-too-large-title = Server 拒绝接收这个文件
server-error-file-too-large-help = 文件可能超过 Server 或代理允许的大小。请尝试较小的 PDF；使用远程服务时，可联系提供者检查上传大小限制。
server-error-file-missing-title = Server 上找不到这个结果文件
server-error-file-missing-help = 请检查任务是否已完成，以及 Server 的输出文件是否被移动或清理。如果结果文件仍在本机，可以手动导入 Zotero。
server-error-http-title = Server 返回错误（HTTP { $status }）
server-error-http-help = 请查看 PDF2zh Server 窗口中的错误提示。使用远程服务时，请确认服务可用，或将下面的技术信息提供给服务维护者。
server-error-phase-check = 本次操作尚未提交文件。连接正常后，再执行操作即可。
server-error-phase-submit = 尚不能确认任务是否提交成功。恢复连接后，请先查看 Server 任务列表，避免重复提交同一篇 PDF。
server-error-phase-poll = 任务已经提交，Server 可能仍在处理。恢复连接后请先查看任务列表，不必立即重新翻译。
server-error-phase-download = 翻译结果可能已经生成。请先检查 Server 的输出文件，恢复连接后再导入，不必立即重新翻译。
server-error-details = 技术信息（反馈问题时可一并提供）：{ $detail }

glossary-no-file = 未选择术语表
glossary-picker = 选择自定义术语表 CSV
glossary-error-format = 请选择非空的 CSV 术语表。
glossary-error-read = 无法读取术语表。请确认文件仍在原位置且使用 UTF-8 编码，或在设置中重新选择。
glossary-error-size = 术语表大小不能超过 1 MiB。
glossary-error-server = 当前 PDF2zh Server 不支持上传术语表。请更新 Server 后重试，或在插件设置中移除已选术语表。
