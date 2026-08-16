# Local Changes

本地维护分支基于上游仓库 `guaguastandup/zotero-pdf2zh` 的提交 `79057f8`（`chore(publish): release v4.0.3`）。

## 服务端

- 增加 `/api/history/delete` 接口。
- 历史记录页面支持逐条删除。
- 新增整文件缓存命中：
  - 以原始 PDF 的 SHA-256 作为文件指纹。
  - 以会影响翻译结果的配置生成 `configHash`。
  - 若两者都一致且目标文件仍存在，则直接返回已有翻译结果。
- 新增持久化元数据数据库：
  - 路径：`server/translated/.pdf2zh_metadata.sqlite3`
  - 用途：历史记录、整文件缓存索引、删除时的引用关系判断。
- 若存在旧版 `server/translated/.pdf2zh_metadata.json`，服务启动时会自动迁移到 SQLite。
- 保留原有 `pdf2zh_next` SQLite 细颗粒缓存逻辑，不做改动。

## 插件

- 插件源码基于上游 `plugin/` 目录中的 `4.0.3` 版本源码修改。
- 仓库根目录附带的 `zotero-pdf-2-zh-v4.0.1.xpi` 只是旧的打包产物，不是这次本地修改的基线。
- 本地插件版本号提升为 `4.0.3-local.1`。
- 已修改文件：
  - `plugin/src/modules/pdf2zhHelper.ts`
- 修改内容：
  - 不再直接对响应调用 `response.json()`
  - 改为先读取响应文本，再尝试 `JSON.parse`
  - 非 JSON 响应时，直接暴露接口名、HTTP 状态码、Content-Type 和响应前 300 个字符
  - 便于定位 `413`、`504`、反向代理 HTML 错误页等问题
