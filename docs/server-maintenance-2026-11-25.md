# Server 更新、打包和发布（2026-11-25）

本轮保持版本 4.1.8，不合并 main、不创建发布标签、不发布 PyPI 或 Docker 镜像。

## 更新策略

同一份 Server 支持：

```sh
python server.py --update-mode=notify
python server.py --update-mode=prompt
python server.py --update-mode=off
```

- `notify`：只检查并提示 Server 新版本，继续启动；不询问、不更新。
- `prompt`：保留源码用户原有的询问方式。Docker 或没有交互终端时仍不询问。
- `off`：关闭 Server 版本检查和启动时的已有翻译环境更新询问。
- 默认仍为 `prompt`，兼容现有桌面启动脚本；Docker 配置明确传 `notify`。
- 旧参数 `--check_update=False` 保留，且优先于新策略。
- `notify/off` 都不会在启动时弹出已有引擎环境的更新询问。首次安装缺少的运行环境仍走原安装流程。
- 公告检查是独立功能，不受版本检查选项影响。

Docker 用户主动在宿主机运行 `sh update.sh`，Windows 用 `./update.ps1`。
默认更新 Server；`all` 才同时拉取翻译引擎。更新前等正在翻译的任务结束。
这不是容器内自我覆盖源码，也不是自动后台升级。当前还是源码构建方式，尚未发布我们自己的预构建镜像。

## 文译默认值

全书预扫、三译合润、润色、审校、注释/链接对齐均默认关闭；Server 缺省请求也明确关闭这些阶段。
保留单语 PDF 输出，否则关掉所有输出将无法完成翻译。用户已明确保存的选择不重置。
三译合润由用户主动选择时仍联动开启润色，界面说明这一关系。
文译是可选实验引擎，不作默认推荐。关闭额外流程不能保证固定耗时或 Token 上限，也不等于禁用引擎内所有术语处理。

## 本地打包：不用删除任何原文件

仓库根目录运行：

```sh
python tools/package_server.py
```

生成 `dist/server.zip` 和 `dist/server.manifest.json`，清单含每个文件和 ZIP 的 SHA-256。
只收集 Git 已跟踪且在允许范围内的文件：服务入口、运行工具、Python utils、页面资源、三份配置模板和安装脚本。
不会打包 `.env*`、真实配置、译文、虚拟环境、文译任务和缓存、测试文件、临时文件、macOS 元数据或任意额外的根目录文件。
新模块需先纳入 Git 跟踪；新增资源类型需修改 `tools/package_server.py` 的允许范围并加测试。
本地文件不移动、不清理、不覆盖。历史根目录 `server.zip` 也不会被本地默认命令覆盖。
这个命令只负责文件范围，不代表通过了密钥扫描或真实翻译测试。

## 准备、提交、发布入口

需先安装 [Gitleaks](https://github.com/gitleaks/gitleaks)，并确保命令在 PATH 中。
本轮实际检查使用 8.30.1；发布工作流固定该版本并校验下载校验和。

```sh
# 本地扫描已跟踪文件（包含 ZIP 内容），然后打包；不提交、不上传
python tools/release.py

# 明确指定要提交的文件，扫描和打包后提交；不上传、不发布
python tools/release.py --commit-message "fix: describe the change" --paths server/server.py

# 未来正式发布时才运行：要求已测试并合并的干净 main，与 origin/main 一致
python tools/release.py --publish
```

禁止将提交和发布放在同一次调用里。已有暂存内容时停止，避免夹带未审查改动。
提交入口拒绝常见私有数据路径、真实配置和打包产物；源码中的假值也可能触发扫描，需要核实，不能直接忽略整个目录。
默认扫描报告保存在 `dist/secret-scan.json`，内容脱敏。`dist` 不纳入 Git。
发布前要求 Plugin/Server 版本一致且标签不存在，运行工具测试、Server 测试、插件测试与构建。
`--publish` 只创建并推送当前版本标签，交由现有 GitHub Release 工作流打包发布，不自动增加版本、不自动推 main、不覆盖旧标签。
GitHub Release 工作流同样进行源码密钥扫描，并复用同一个 Server 打包工具；本地和云端不再维护两份排除清单。
发布触发后仍需确认 Actions 成功；若推送标签失败，检查网络和本地标签状态，不能盲目反复创建标签。
当前存在未跟踪的旧 XPI，正式发布前应由维护者移到仓库外保存，工具不会替你删除它。

## PyPI：维护者需要完成的流程

2026-11-25 查询 PyPI JSON API，`zotero-pdf2zh-server`、`zotero-pdf2zh`、
`zotero-pdf-to-zh-server` 均返回 404。只说明当前没有可查询的公开项目，不能保证名字可注册，也不能确认历史所有者。
大小写以及连字符、下划线、点的变体不能当作不同项目来绕过名称占用。

1. 在 [PyPI](https://pypi.org/account/register/) 创建/登录自己的维护者账号，验证邮箱、启用双因素验证并保存恢复码。
2. 确定最终包名。若已占用，先联系维护者请求转移/加入 Owner；不符合转移条件或不想等待时选择新名称。
   官方源码作者身份不会自动获得他人 PyPI 项目的发布权限。废弃名称申请按 PyPI 的名称保留规则处理。
3. 我们先把 Server 制作成可安装的 wheel/sdist，处理用户数据目录与命令入口，填写官网和官方仓库链接。
   这部分本轮没有实施；当前 ZIP 发布工具不等于 PyPI 发布工具。
4. 注册独立的 TestPyPI 账号，先在测试索引验证构建、安装、启动、配置保留和卸载行为。
5. 在 PyPI 的账号 Publishing 页面添加 Pending Trusted Publisher：owner 为 `guaguastandup`，repository 为 `zotero-pdf2zh`，
   workflow 文件名须与未来实际创建的 PyPI 发布工作流一致，例如 `publish-pypi.yml`，environment 建议 `pypi`。
   GitHub 对应环境设置审批；工作流使用短期身份令牌，无需保存长期 PyPI 密钥。
6. 验证后首次上传创建项目，再核对项目 Owner、项目链接、安装命令和发布来源。
   Pending Publisher 本身不保留名称，最终是否可用以 PyPI 接受发布为准。

官方参考：
- [选择项目名](https://docs.pypi.org/project-management/choosing-a-name/)
- [名称转移规则](https://peps.python.org/pep-0541/)
- [首次通过 Trusted Publisher 创建项目](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/)
- [发布包](https://docs.pypi.org/publishing/publishing-to-pypi/)

## 合并与手工验收

本轮开始时，当前分支比 origin/main 多 4 个提交、落后 0 个。提交中含一次较大修改及后续缩小范围的提交，不能只按提交数量估计测试量。
推荐：保留 main 基准 → 在当前分支测试构建 → 修复 → 合并 main → 用同一提交再做简短确认。
不必先合入 main 才能测试：直接安装当前分支构建的 XPI，并运行本分支打出的 Server。
如确实先合并，至少不发布版本，保留明确的基准，并用新的 revert 提交回退，不重写已推送历史。

优先人工验证：
- Zotero 启动/重启、设置窗口、已有 LLM 配置切换；新配置不会残留上一服务字段。
- Server 未启动时的提示；重新启动后可正常翻译。
- pdf2zh-next 单语/双语、crop-compare 第二页、用户术语表。
- 文译初次打开全部额外选项关闭；主动勾选后重开仍保留；三译合润联动润色。
- Docker 启动只提示更新；容器内配置/术语表临时文件能被实际翻译子容器访问。
- 关闭 Server 再启动后配置、译文保留。

真实 Zotero、Docker 构建、模型调用和长论文耗时没有被本轮自动测试替代。
Server 后续优先小步改进：任务状态/超时/取消、临时文件在 Docker 子容器中的可见性、诊断信息脱敏、配置和程序目录分离、可安装 Python 包。
不要同时重写翻译流程和发布体系。

## 本轮验证结果

- 插件 100 项测试、TypeScript 检查、格式和 lint、生产构建均通过。
- Server 全套发现 198 项：183 项通过，15 项因缺少对应上游包/运行环境或未启用外部集成条件跳过。
- 打包/发布入口 8 项测试通过（临时仓库、假扫描器验证操作边界）；另使用真实 Gitleaks 扫描当前源码/历史/压缩包。
- 实际生成的 Server ZIP 解压后 `server.py --enable_venv=False --update-mode=notify --help` 成功退出并包含更新策略参数。
- 未执行真正的 `--publish`、PyPI 上传或 Docker 构建。插件构建工具首次写缓存受限，随后完整重跑成功。
