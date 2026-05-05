"""Babeldoc 翻译缓存探查器: 暴露缓存条目数和翻译完成后的 delta。

babeldoc 在 ~/.cache/babeldoc/cache.v1.db 维护一个 sqlite 表
`_translationcache(translate_engine, translate_engine_params, original_text, translation)`，
按 unique (engine, params, original_text) 缓存翻译结果。

我们利用这个 db 给前端展示两类信息：

1. 全局缓存规模（GET /api/cache-stats）—— 让用户知道缓存累积了多少条目。
2. 单次翻译的 cache delta —— 翻译开始/结束时记录行数差，得出本次实际"新发起 LLM 调用"的段落数。
"""

from __future__ import annotations

import os
import sqlite3
from typing import Optional

# babeldoc 默认缓存路径; 若 BABELDOC_CACHE_DIR 环境变量被设置则用它
def _candidate_paths():
    """生成候选 db 路径. BABELDOC_CACHE_DIR 设置时只用它, 不再 fallback 默认路径
    (Codex review #300 P2: 否则用户明确指定的位置无效但不知).
    """
    explicit = os.environ.get("BABELDOC_CACHE_DIR")
    if explicit:
        explicit = os.path.expanduser(explicit)
        # 既支持指向目录也支持指向 .db 文件
        if os.path.isdir(explicit):
            return [os.path.join(explicit, "cache.v1.db")]
        return [explicit]
    return [os.path.expanduser("~/.cache/babeldoc/cache.v1.db")]


def _find_db() -> Optional[str]:
    for p in _candidate_paths():
        if os.path.isfile(p):
            return p
    return None


def get_global_stats() -> dict:
    """返回全局缓存信息: 总条目数, 库文件大小 MB, 涉及的 engine 列表.

    注意: 不返回 dbPath, 避免向 server 监听网络的客户端泄漏本机文件系统结构.
    路径在 babeldoc 项目里是固定的 (~/.cache/babeldoc/cache.v1.db), 客户端
    不需要它.
    """
    db = _find_db()
    if not db:
        return {"available": False, "reason": "babeldoc cache db not found"}
    try:
        size_bytes = os.path.getsize(db)
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            cur = conn.cursor()
            total = cur.execute(
                "SELECT COUNT(*) FROM _translationcache"
            ).fetchone()[0]
            engines = [
                row[0]
                for row in cur.execute(
                    "SELECT DISTINCT translate_engine FROM _translationcache "
                    "ORDER BY translate_engine"
                )
            ]
        return {
            "available": True,
            # 不暴露 dbPath, 防止向局域网泄漏文件系统信息
            "totalEntries": total,
            "sizeMb": round(size_bytes / 1024 / 1024, 2),
            "engines": engines,
            "schemaTable": "_translationcache",  # 标明依赖的 babeldoc 内部 schema
        }
    except Exception as e:
        # codex review #300 P2: 不返回 raw 异常文本, 因为 OSError/PermissionError 会
        # 在 message 里嵌入完整文件路径 (例如 "Permission denied: '/Users/x/.cache/...'"),
        # 这违反了 v2 移除 dbPath 的 LAN 信息隐藏目标. 服务端日志正常打印, 客户端只看通用错误码.
        print(f"[cache_inspector] read failed: {e}", flush=True)
        return {"available": False, "reason": "cache_db_read_error"}


def count_entries() -> Optional[int]:
    """快速返回当前缓存条目数, 失败返回 None"""
    db = _find_db()
    if not db:
        return None
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            return conn.execute(
                "SELECT COUNT(*) FROM _translationcache"
            ).fetchone()[0]
    except Exception:
        return None
