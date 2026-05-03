import json
import os
import threading
import time
from datetime import datetime


# DEBUG_PROGRESS_LOG_PATH = os.path.join(
#     os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
#     "_debug_progress.log",
# )
# _DEBUG_LOG_LOCK = threading.Lock()


# def _debug_progress_log(stage, **fields):
#     try:
#         ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
#         parts = []
#         for key in sorted(fields.keys()):
#             value = str(fields[key]).replace("\r", "\\r").replace("\n", "\\n")
#             if len(value) > 800:
#                 value = value[:800] + "..."
#             parts.append(f"{key}={value}")
#         line = f"[{ts}] [{stage}] " + " ".join(parts)
#         with _DEBUG_LOG_LOCK:
#             with open(DEBUG_PROGRESS_LOG_PATH, "a", encoding="utf-8", errors="replace") as fp:
#                 fp.write(line + "\n")
#     except Exception:
#         pass


class TaskManager:
    def __init__(self):
        self.active_tasks = {}
        self.lock = threading.Lock()
        self.progress_history = []
        self.store = None

    def set_store(self, store):
        self.store = store

    @staticmethod
    def _task_snapshot(task_id, task):
        snapshot = {
            "taskId": task_id,
            "fileName": task.get("fileName"),
            "active": task.get("active"),
            "progress": task.get("progress"),
            "status": task.get("status"),
            "message": task.get("message"),
            "engine": task.get("engine"),
            "service": task.get("service"),
        }
        return json.dumps(snapshot, ensure_ascii=False, sort_keys=True)

    def add_task(self, task_id, info):
        with self.lock:
            self.active_tasks[task_id] = info
            # _debug_progress_log("TASK_ADD", task=self._task_snapshot(task_id, self.active_tasks[task_id]))

    def update_task(self, task_id, updates):
        with self.lock:
            if task_id in self.active_tasks:
                self.active_tasks[task_id].update(updates)
                # _debug_progress_log(
                #     "TASK_UPDATE",
                #     updates=json.dumps(updates, ensure_ascii=False, sort_keys=True),
                #     task=self._task_snapshot(task_id, self.active_tasks[task_id]),
                # )

    def complete_task(self, task_id, status, message=None, file_list=None, error=None):
        with self.lock:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                task["active"] = False
                task["status"] = "完成" if status == "success" else "失败"
                task["progress"] = 100 if status == "success" else task.get("progress", 0)
                if message:
                    task["message"] = message
                task["endTime"] = datetime.now().isoformat()

                history_item = {
                    "id": task_id,
                    "fileName": task.get("fileName"),
                    "status": "success" if status == "success" else "failed",
                    "engine": task.get("engine"),
                    "service": task.get("service"),
                    "modelName": task.get("modelName"),
                    "startTime": task.get("startTime"),
                    "endTime": task.get("endTime"),
                    "config": task.get("config"),
                    "sourceFile": task.get("sourceFile"),
                    "fileHash": task.get("fileHash"),
                    "configHash": task.get("configHash"),
                    "cacheHit": bool(task.get("cacheHit")),
                }
                if file_list:
                    history_item["fileList"] = list(file_list)
                if error:
                    history_item["error"] = str(error)

                self.progress_history.insert(0, history_item)
                if len(self.progress_history) > 200:
                    self.progress_history = self.progress_history[:200]
                if self.store:
                    self.store.upsert_history(history_item)

                # _debug_progress_log(
                #     "TASK_COMPLETE",
                #     status=status,
                #     task=self._task_snapshot(task_id, task),
                #     file_list=json.dumps(file_list or [], ensure_ascii=False),
                #     error=str(error) if error is not None else "",
                # )

                threading.Thread(target=self._delayed_remove, args=(task_id,), daemon=True).start()

    def get_active_tasks_list(self):
        with self.lock:
            tasks = list(self.active_tasks.values())
            return tasks

    def get_history(self):
        if self.store:
            return self.store.get_history()
        with self.lock:
            return list(self.progress_history)

    def get_active_referenced_files(self):
        with self.lock:
            referenced = set()
            for task in self.active_tasks.values():
                if not task.get("active"):
                    continue
                source_file = task.get("sourceFile")
                if source_file:
                    referenced.add(source_file)
            return referenced

    def delete_history(self, history_id):
        with self.lock:
            target = None
            remaining = []
            for item in self.progress_history:
                if target is None and item.get("id") == history_id:
                    target = item
                    continue
                remaining.append(item)
            self.progress_history = remaining
        if self.store:
            protected_files = self.get_active_referenced_files()
            store_target, deleted_files = self.store.delete_history(
                history_id,
                protected_files=protected_files,
            )
            return store_target or target, deleted_files
        return target, []

    def clear_history(self):
        with self.lock:
            self.progress_history = []
        if self.store:
            protected_files = self.get_active_referenced_files()
            return self.store.clear_history(protected_files=protected_files)
        return []

    def _delayed_remove(self, task_id):
        time.sleep(30)
        with self.lock:
            if task_id in self.active_tasks:
                # _debug_progress_log("TASK_REMOVE", task_id=task_id)
                del self.active_tasks[task_id]


# global singleton
task_manager = TaskManager()
