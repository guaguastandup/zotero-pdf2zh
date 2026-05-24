import json
import os
import shutil
import sqlite3
import threading


class MetadataStore:
    def __init__(
        self,
        output_folder,
        db_filename=".pdf2zh_metadata.sqlite3",
        legacy_filename=".pdf2zh_metadata.json",
    ):
        self.output_folder = os.path.abspath(output_folder)
        self.path = os.path.join(self.output_folder, db_filename)
        self.legacy_path = os.path.join(self.output_folder, legacy_filename)
        self.lock = threading.Lock()
        os.makedirs(self.output_folder, exist_ok=True)
        with self.lock:
            self._initialize_unlocked()

    def _initialize_unlocked(self):
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS history (
                    id TEXT PRIMARY KEY,
                    file_name TEXT,
                    status TEXT,
                    engine TEXT,
                    service TEXT,
                    model_name TEXT,
                    start_time TEXT,
                    end_time TEXT,
                    config_json TEXT,
                    source_file TEXT,
                    file_hash TEXT,
                    config_hash TEXT,
                    cache_hit INTEGER NOT NULL DEFAULT 0,
                    error TEXT,
                    file_list_json TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_history_result_ref
                ON history(file_hash, config_hash, start_time DESC)
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache_entries (
                    file_hash TEXT NOT NULL,
                    config_hash TEXT NOT NULL,
                    file_list_json TEXT NOT NULL,
                    engine TEXT,
                    service TEXT,
                    model_name TEXT,
                    updated_at TEXT,
                    PRIMARY KEY (file_hash, config_hash)
                )
                """
            )
            conn.commit()
            self._migrate_legacy_json_unlocked(conn)

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _migrate_legacy_json_unlocked(self, conn):
        if not os.path.exists(self.legacy_path):
            return

        has_history = conn.execute("SELECT 1 FROM history LIMIT 1").fetchone()
        has_cache = conn.execute("SELECT 1 FROM cache_entries LIMIT 1").fetchone()
        if has_history or has_cache:
            return

        try:
            with open(self.legacy_path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except Exception:
            return

        if not isinstance(payload, dict):
            return

        for item in payload.get("history", []) or []:
            if isinstance(item, dict):
                self._upsert_history_unlocked(conn, item)

        for entry in payload.get("cache_entries", []) or []:
            if isinstance(entry, dict):
                self._upsert_cache_entry_unlocked(conn, entry)

        conn.commit()

        backup_path = f"{self.legacy_path}.migrated.bak"
        try:
            if os.path.exists(backup_path):
                os.remove(self.legacy_path)
            else:
                os.replace(self.legacy_path, backup_path)
        except OSError:
            pass

    def upsert_history(self, item):
        with self.lock:
            with self._connect() as conn:
                self._upsert_history_unlocked(conn, item)
                conn.commit()

    def _upsert_history_unlocked(self, conn, item):
        payload = self._normalize_history(item)
        conn.execute(
            """
            INSERT INTO history (
                id, file_name, status, engine, service, model_name,
                start_time, end_time, config_json, source_file,
                file_hash, config_hash, cache_hit, error, file_list_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                file_name = excluded.file_name,
                status = excluded.status,
                engine = excluded.engine,
                service = excluded.service,
                model_name = excluded.model_name,
                start_time = excluded.start_time,
                end_time = excluded.end_time,
                config_json = excluded.config_json,
                source_file = excluded.source_file,
                file_hash = excluded.file_hash,
                config_hash = excluded.config_hash,
                cache_hit = excluded.cache_hit,
                error = excluded.error,
                file_list_json = excluded.file_list_json
            """,
            (
                payload["id"],
                payload["file_name"],
                payload["status"],
                payload["engine"],
                payload["service"],
                payload["model_name"],
                payload["start_time"],
                payload["end_time"],
                payload["config_json"],
                payload["source_file"],
                payload["file_hash"],
                payload["config_hash"],
                payload["cache_hit"],
                payload["error"],
                payload["file_list_json"],
            ),
        )

    def get_history(self):
        with self.lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM history
                    ORDER BY start_time DESC, id DESC
                    """
                ).fetchall()
                return [self._history_from_row(row) for row in rows]

    def upsert_cache_entry(self, entry):
        with self.lock:
            with self._connect() as conn:
                self._upsert_cache_entry_unlocked(conn, entry)
                conn.commit()

    def _upsert_cache_entry_unlocked(self, conn, entry):
        payload = self._normalize_cache_entry(entry)
        if not payload["file_hash"] or not payload["config_hash"]:
            return
        if not payload["file_list"]:
            return

        conn.execute(
            """
            INSERT INTO cache_entries (
                file_hash, config_hash, file_list_json, engine,
                service, model_name, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(file_hash, config_hash) DO UPDATE SET
                file_list_json = excluded.file_list_json,
                engine = excluded.engine,
                service = excluded.service,
                model_name = excluded.model_name,
                updated_at = excluded.updated_at
            """,
            (
                payload["file_hash"],
                payload["config_hash"],
                payload["file_list_json"],
                payload["engine"],
                payload["service"],
                payload["model_name"],
                payload["updated_at"],
            ),
        )

    def get_cache_entry(self, file_hash, config_hash):
        with self.lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT * FROM cache_entries
                    WHERE file_hash = ? AND config_hash = ?
                    """,
                    (file_hash, config_hash),
                ).fetchone()
                if row is None:
                    return None

                entry = self._cache_entry_from_row(row)
                if self._entry_files_exist(entry.get("fileList") or []):
                    return entry

                conn.execute(
                    """
                    DELETE FROM cache_entries
                    WHERE file_hash = ? AND config_hash = ?
                    """,
                    (file_hash, config_hash),
                )
                conn.commit()
                return None

    def delete_history(self, history_id, protected_files=None):
        with self.lock:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM history WHERE id = ?",
                    (history_id,),
                ).fetchone()
                if row is None:
                    return None, []

                target = self._history_from_row(row)
                conn.execute("DELETE FROM history WHERE id = ?", (history_id,))

                file_hash = target.get("fileHash")
                config_hash = target.get("configHash")
                if file_hash and config_hash:
                    still_referenced = conn.execute(
                        """
                        SELECT 1 FROM history
                        WHERE file_hash = ? AND config_hash = ?
                        LIMIT 1
                        """,
                        (file_hash, config_hash),
                    ).fetchone()
                    if not still_referenced:
                        conn.execute(
                            """
                            DELETE FROM cache_entries
                            WHERE file_hash = ? AND config_hash = ?
                            """,
                            (file_hash, config_hash),
                        )

                referenced_files = self._collect_referenced_files_unlocked(conn)
                candidate_files = self._history_cleanup_candidates(target)

                deleted_files = []
                protected_files = set(protected_files or [])
                for filename in dict.fromkeys(candidate_files):
                    if (
                        not filename
                        or filename in referenced_files
                        or filename in protected_files
                    ):
                        continue
                    if self._safe_remove_path(filename):
                        deleted_files.append(filename)

                self._prune_stale_cache_entries_unlocked(conn)
                conn.commit()
                return target, deleted_files

    def clear_history(self, protected_files=None):
        with self.lock:
            with self._connect() as conn:
                deleted_files = self._delete_all_visible_files_unlocked(
                    protected_files=protected_files,
                )
                conn.execute("DELETE FROM history")
                conn.execute("DELETE FROM cache_entries")
                conn.commit()
                return deleted_files

    def _collect_referenced_files_unlocked(self, conn):
        referenced = set()

        history_rows = conn.execute(
            "SELECT source_file, file_list_json FROM history"
        ).fetchall()
        for row in history_rows:
            source_file = row["source_file"]
            if source_file:
                referenced.add(source_file)
            file_list = self._parse_json_list(row["file_list_json"])
            for filename in file_list:
                if filename:
                    referenced.add(filename)
            for filename in self._history_cleanup_candidates({
                "engine": row["engine"],
                "sourceFile": source_file,
                "fileList": file_list,
            }):
                if filename:
                    referenced.add(filename)

        cache_rows = conn.execute(
            "SELECT file_list_json FROM cache_entries"
        ).fetchall()
        for row in cache_rows:
            for filename in self._parse_json_list(row["file_list_json"]):
                if filename:
                    referenced.add(filename)

        return referenced

    def _prune_stale_cache_entries_unlocked(self, conn):
        rows = conn.execute(
            "SELECT file_hash, config_hash, file_list_json FROM cache_entries"
        ).fetchall()
        stale_keys = []
        for row in rows:
            file_list = self._parse_json_list(row["file_list_json"])
            if not self._entry_files_exist(file_list):
                stale_keys.append((row["file_hash"], row["config_hash"]))

        if stale_keys:
            conn.executemany(
                """
                DELETE FROM cache_entries
                WHERE file_hash = ? AND config_hash = ?
                """,
                stale_keys,
            )

    def _delete_all_visible_files_unlocked(self, protected_files=None):
        deleted_files = []
        protected_files = set(protected_files or [])

        for root, dirnames, filenames in os.walk(self.output_folder, topdown=False):
            dirnames[:] = [name for name in dirnames if not name.startswith(".")]

            for filename in filenames:
                if filename.startswith("."):
                    continue
                abs_path = os.path.join(root, filename)
                rel_path = os.path.relpath(abs_path, self.output_folder)
                if rel_path in protected_files:
                    continue
                if self._safe_remove_file(rel_path):
                    deleted_files.append(rel_path)

            if os.path.abspath(root) == self.output_folder:
                continue

            rel_dir = os.path.relpath(root, self.output_folder)
            if rel_dir.startswith("."):
                continue
            try:
                os.rmdir(root)
            except OSError:
                pass

        return sorted(deleted_files)

    def _normalize_history(self, item):
        return {
            "id": item.get("id"),
            "file_name": item.get("fileName"),
            "status": item.get("status"),
            "engine": item.get("engine"),
            "service": item.get("service"),
            "model_name": item.get("modelName"),
            "start_time": item.get("startTime"),
            "end_time": item.get("endTime"),
            "config_json": self._dump_json(item.get("config")),
            "source_file": item.get("sourceFile"),
            "file_hash": item.get("fileHash"),
            "config_hash": item.get("configHash"),
            "cache_hit": 1 if item.get("cacheHit") else 0,
            "error": item.get("error"),
            "file_list_json": self._dump_json(item.get("fileList") or []),
        }

    def _history_from_row(self, row):
        data = {
            "id": row["id"],
            "fileName": row["file_name"],
            "status": row["status"],
            "engine": row["engine"],
            "service": row["service"],
            "modelName": row["model_name"],
            "startTime": row["start_time"],
            "endTime": row["end_time"],
            "sourceFile": row["source_file"],
            "fileHash": row["file_hash"],
            "configHash": row["config_hash"],
            "cacheHit": bool(row["cache_hit"]),
        }

        config = self._load_json(row["config_json"])
        if config is not None:
            data["config"] = config

        file_list = self._parse_json_list(row["file_list_json"])
        if file_list:
            data["fileList"] = file_list

        if row["error"]:
            data["error"] = row["error"]

        return data

    def _normalize_cache_entry(self, entry):
        file_list = entry.get("fileList") or []
        return {
            "file_hash": entry.get("fileHash"),
            "config_hash": entry.get("configHash"),
            "file_list": list(file_list),
            "file_list_json": self._dump_json(file_list),
            "engine": entry.get("engine"),
            "service": entry.get("service"),
            "model_name": entry.get("modelName"),
            "updated_at": entry.get("updatedAt"),
        }

    def _cache_entry_from_row(self, row):
        return {
            "fileHash": row["file_hash"],
            "configHash": row["config_hash"],
            "fileList": self._parse_json_list(row["file_list_json"]),
            "engine": row["engine"],
            "service": row["service"],
            "modelName": row["model_name"],
            "updatedAt": row["updated_at"],
        }

    @staticmethod
    def _dump_json(value):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)

    @staticmethod
    def _load_json(value):
        if not value:
            return None
        try:
            return json.loads(value)
        except Exception:
            return None

    def _parse_json_list(self, value):
        parsed = self._load_json(value)
        if isinstance(parsed, list):
            return parsed
        return []

    def _entry_files_exist(self, file_list):
        return bool(file_list) and all(self._file_exists(name) for name in file_list)

    def _file_exists(self, filename):
        file_path = self._safe_join(filename)
        return bool(file_path) and os.path.exists(file_path)

    def _safe_remove_file(self, filename):
        file_path = self._safe_join(filename)
        if not file_path or not os.path.exists(file_path):
            return False
        os.remove(file_path)
        return True

    def _safe_remove_path(self, filename):
        file_path = self._safe_join(filename)
        if not file_path or not os.path.exists(file_path):
            return False
        if os.path.isdir(file_path):
            if os.path.abspath(file_path) == self.output_folder:
                return False
            shutil.rmtree(file_path)
            return True
        os.remove(file_path)
        return True

    def _history_cleanup_candidates(self, item):
        candidates = []
        source_file = item.get("sourceFile")
        file_list = list(item.get("fileList") or [])
        if source_file:
            candidates.append(source_file)
        candidates.extend(file_list)

        engine = (item.get("engine") or "").lower()
        if engine == "skim" or any("_skim" in (name or "") for name in file_list):
            for filename in [source_file, *file_list]:
                asset_dir = self._skim_asset_dir_for(filename)
                if asset_dir:
                    candidates.append(asset_dir)
        return candidates

    @staticmethod
    def _skim_asset_dir_for(filename):
        if not filename:
            return ""
        directory = os.path.dirname(filename)
        basename = os.path.basename(filename)
        stem = os.path.splitext(basename)[0]
        if stem.endswith("_skim"):
            stem = stem[:-len("_skim")]
        if not stem:
            return ""
        asset_dir = f"{stem}_skim_assets"
        return os.path.join(directory, asset_dir) if directory else asset_dir

    def _safe_join(self, filename):
        full = os.path.abspath(os.path.join(self.output_folder, filename))
        if os.path.commonpath([self.output_folder, full]) != self.output_folder:
            return None
        return full
