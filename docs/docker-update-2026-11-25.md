# Docker 更新入口与编码依赖核对

本轮为源码更新，不更改版本号，不重打 docker.zip/server.zip，不发布镜像。

## 更新行为

- `docker/update.sh` / `docker/update.ps1` 在宿主机执行，默认仅重建 Server。
- 传入 `all` 后同时拉取 Compose 实际配置的子引擎镜像。
- 保留现有下载地址、代理及挂载配置；先构建，成功后才重建服务。
- 不运行 down、删除卷或 prune；失败中止，非零退出。
- Docker 内的 Server 源码更新和托管依赖更新不再请求交互输入，即便分配了 TTY。
- 两种 Docker 启动方式显式监听 0.0.0.0，以便宿主机端口映射访问。
- docker2 的引擎集成在基础镜像内，使用其文档中的 build/up 命令，不能套用子引擎拉取脚本。

脚本更新的是所配置 URL 对应的 server.zip；固定版本不会自动变成最新版，
未打包发布的开发源码也不会因为执行脚本而进入已有镜像。

## charset 核对与复现

2026-11-25 的 PyPI 信息为 charset-normalizer 3.5.3、chardet 7.7.0、Requests 2.34.2。
在全新临时 Python 3.13 环境中，仅导入 Requests，结果如下。

| Requests | charset-normalizer | chardet | 结果 |
| --- | --- | --- | --- |
| 2.32.3 | 3.5.3 | 7.7.0 | RequestsDependencyWarning |
| 2.32.3 | 3.5.3 | 未安装 | 无警告 |
| 2.34.2 | 3.5.3 | 7.7.0 | 无警告 |

这三个用例的 urllib3 均为 2.8.0。旧 Requests 优先检查已安装的 chardet，
要求 <6；charset-normalizer 仍满足 >=2,<4。不能只看警告中出现 charset 就降级它。
这是隔离环境复现，不代表已取得反馈用户容器的实际包版本。
`server/check_charset.py` 提供只读诊断，须使用实际报错引擎的 Python 运行。
本轮没有调整运行依赖约束。

来源：[PyPI](https://pypi.org/project/charset-normalizer/)、
[Requests 2.32.3 检查逻辑](https://github.com/psf/requests/blob/v2.32.3/src/requests/__init__.py)、
[Requests 当前依赖声明](https://github.com/psf/requests/blob/main/pyproject.toml)。

## 验证与待办

- 7 项新离线测试及 8 项依赖基线测试通过；shell 语法、Python 编译和差异检查通过。
- 模拟 Docker 命令验证成功顺序、构建/拉取失败中止、非法参数拒绝及不删除卷。
- 本机没有 Docker CLI 和 PowerShell，未实际构建/重建镜像，PowerShell 脚本未实机运行。
- 发布前仍需在 Docker 实测配置保留、下载代理、重建后的健康检查。
- 当前开发分支新增的任务临时配置和术语表使用系统临时目录；docker/ 子引擎通过
  volumes-from 继承挂载，不能直接读取 Server 容器未挂载的 /tmp。
  这属于独立的跨容器文件兼容问题，本轮没有扩大修改；开发分支打包发布前必须单独处理。
