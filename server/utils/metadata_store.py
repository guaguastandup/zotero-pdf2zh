import json
import os
import threading
from copy import deepcopy


class MetadataStore:
    def __init__(self, output_folder, filename=".pdf2zh_metadata.json"):
        self.output_folder = os.path.abspath(output_folder)
        self.path = os.path.join(self.output_folder, filename)
        self.lock = threading.Lock()
        os.makedirs(self.output_folder, exist_ok=True)
        if not os.path.exists(self.path):
            self._save_unlocked(self._default_data())

    @staticmethod
    def _default_data():
        return {
            "version": 1,
            "history": [],
            "cache_entries": [],
        }

    def _load_unlocked(self):
        if not os.path.exists(self.path):
            return self._default_data()
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return self._default_data()

        if not isinstance(data, dict):
            return self._default_data()
        data.setdefault("version", 1)
        data.setdefault("history", [])
        data.setdefault("cache_entries", [])
        return data

    def _save_unlocked(self, data):
        tmp_path = f"{self.path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, self.path)

    def upsert_history(self, item):
        with self.lock:
            data = self._load_unlocked()
            history = data["history"]
            replaced = False
            for idx, existing in enumerate(history):
                if existing.get("id") == item.get("id"):
                    history[idx] = deepcopy(item)
                    replaced = True
                    break
            if not replaced:
                history.append(deepcopy(item))
            data["history"] = sorted(
                history,
                key=lambda x: x.get("startTime") or "",
                reverse=True,
            )
            self._save_unlocked(data)

    def get_history(self):
        with self.lock:
            data = self._load_unlocked()
            return sorted(
                deepcopy(data["history"]),
                key=lambda x: x.get("startTime") or "",
                reverse=True,
            )

    def upsert_cache_entry(self, entry):
        with self.lock:
            data = self._load_unlocked()
            cache_entries = data["cache_entries"]
            replaced = False
            for idx, existing in enumerate(cache_entries):
                if (
                    existing.get("fileHash") == entry.get("fileHash")
                    and existing.get("configHash") == entry.get("configHash")
                ):
                    cache_entries[idx] = deepcopy(entry)
                    replaced = True
                    break
            if not replaced:
                cache_entries.append(deepcopy(entry))
            data["cache_entries"] = cache_entries
            self._save_unlocked(data)

    def get_cache_entry(self, file_hash, config_hash):
        with self.lock:
            data = self._load_unlocked()
            cache_entries = data["cache_entries"]
            modified = False
            hit = None
            next_entries = []
            for entry in cache_entries:
                if not self._entry_files_exist(entry):
                    modified = True
                    continue
                next_entries.append(entry)
                if (
                    entry.get("fileHash") == file_hash
                    and entry.get("configHash") == config_hash
                ):
                    hit = deepcopy(entry)
            if modified:
                data["cache_entries"] = next_entries
                self._save_unlocked(data)
            return hit

    def delete_history(self, history_id):
        with self.lock:
            data = self._load_unlocked()
            history = data["history"]
            target = None
            remaining_history = []
            for item in history:
                if item.get("id") == history_id:
                    target = item
                else:
                    remaining_history.append(item)

            if target is None:
                return None, []

            data["history"] = remaining_history
            file_hash = target.get("fileHash")
            config_hash = target.get("configHash")
            if file_hash and config_hash:
                has_same_result_ref = any(
                    item.get("fileHash") == file_hash
                    and item.get("configHash") == config_hash
                    for item in remaining_history
                )
                if not has_same_result_ref:
                    data["cache_entries"] = [
                        entry
                        for entry in data["cache_entries"]
                        if not (
                            entry.get("fileHash") == file_hash
                            and entry.get("configHash") == config_hash
                        )
                    ]

            referenced_files = self._collect_referenced_files_unlocked(data)
            candidate_files = []
            candidate_files.extend(target.get("fileList") or [])
            if target.get("sourceFile"):
                candidate_files.append(target.get("sourceFile"))

            deleted_files = []
            for filename in dict.fromkeys(candidate_files):
                if not filename or filename in referenced_files:
                    continue
                if self._safe_remove_file(filename):
                    deleted_files.append(filename)

            self._prune_stale_cache_entries_unlocked(data)
            self._save_unlocked(data)
            return deepcopy(target), deleted_files

    def _collect_referenced_files_unlocked(self, data):
        referenced = set()
        for item in data["history"]:
            for filename in item.get("fileList") or []:
                if filename:
                    referenced.add(filename)
            source_file = item.get("sourceFile")
            if source_file:
                referenced.add(source_file)
        for entry in data["cache_entries"]:
            for filename in entry.get("fileList") or []:
                if filename:
                    referenced.add(filename)
        return referenced

    def _prune_stale_cache_entries_unlocked(self, data):
        data["cache_entries"] = [
            entry for entry in data["cache_entries"] if self._entry_files_exist(entry)
        ]

    def _entry_files_exist(self, entry):
        file_list = entry.get("fileList") or []
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

    def _safe_join(self, filename):
        full = os.path.abspath(os.path.join(self.output_folder, filename))
        if os.path.commonpath([self.output_folder, full]) != self.output_folder:
            return None
        return full
