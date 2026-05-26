import json
import os
import threading
import time
from datetime import datetime


class TaskCancelledError(RuntimeError):
    pass


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
        self.active_keys = {}
        self.task_events = {}
        self.task_results = {}
        self.processes = {}
        self.cancelled_task_ids = set()
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

    def add_task(self, task_id, info, dedupe_key=None):
        with self.lock:
            if dedupe_key:
                existing_id = self.active_keys.get(dedupe_key)
                existing = self.active_tasks.get(existing_id)
                if existing and existing.get("active"):
                    existing["waiterCount"] = int(existing.get("waiterCount") or 0) + 1
                    return False, dict(existing)

            info = dict(info)
            info["taskId"] = task_id
            if dedupe_key:
                info["dedupeKey"] = dedupe_key
            self.active_tasks[task_id] = info
            self.task_events[task_id] = threading.Event()
            if dedupe_key:
                self.active_keys[dedupe_key] = task_id
            # _debug_progress_log("TASK_ADD", task=self._task_snapshot(task_id, self.active_tasks[task_id]))
            return True, dict(info)

    def update_task(self, task_id, updates):
        with self.lock:
            if task_id in self.active_tasks:
                if self.active_tasks[task_id].get("terminalStatus"):
                    return
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
                if task.get("terminalStatus"):
                    return self.task_results.get(task_id)

                normalized_status = self._normalize_terminal_status(status)
                task["active"] = False
                task["terminalStatus"] = normalized_status
                task["status"] = self._display_status(normalized_status)
                task["progress"] = 100 if normalized_status == "success" else task.get("progress", 0)
                if message:
                    task["message"] = message
                task["endTime"] = datetime.now().isoformat()

                history_item = {
                    "id": task_id,
                    "fileName": task.get("fileName"),
                    "status": normalized_status,
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
                cleanup_files = task.get("cleanupFiles") or []
                if cleanup_files:
                    history_item["cleanupFiles"] = list(cleanup_files)
                if error:
                    history_item["error"] = str(error)

                dedupe_key = task.get("dedupeKey")
                if dedupe_key and self.active_keys.get(dedupe_key) == task_id:
                    del self.active_keys[dedupe_key]

                self.progress_history.insert(0, history_item)
                if len(self.progress_history) > 200:
                    self.progress_history = self.progress_history[:200]
                if self.store:
                    self.store.upsert_history(history_item)
                self.task_results[task_id] = history_item
                event = self.task_events.get(task_id)
                if event:
                    event.set()

                # _debug_progress_log(
                #     "TASK_COMPLETE",
                #     status=status,
                #     task=self._task_snapshot(task_id, task),
                #     file_list=json.dumps(file_list or [], ensure_ascii=False),
                #     error=str(error) if error is not None else "",
                # )

                threading.Thread(target=self._delayed_remove, args=(task_id,), daemon=True).start()
                return history_item
            return self.task_results.get(task_id)

    @staticmethod
    def _normalize_terminal_status(status):
        if status == "success":
            return "success"
        if status in ("cancel", "cancelled", "canceled"):
            return "cancelled"
        return "failed"

    @staticmethod
    def _display_status(status):
        if status == "success":
            return "完成"
        if status == "cancelled":
            return "已取消"
        return "失败"

    def wait_for_task(self, task_id, timeout=None):
        with self.lock:
            result = self.task_results.get(task_id)
            event = self.task_events.get(task_id)
        if result:
            return result
        if not event:
            return None
        if not event.wait(timeout=timeout):
            return None
        with self.lock:
            return self.task_results.get(task_id)

    def register_process(self, task_id, process):
        if not task_id or process is None:
            return
        with self.lock:
            if task_id in self.active_tasks:
                self.processes[task_id] = process

    def unregister_process(self, task_id, process=None):
        if not task_id:
            return
        with self.lock:
            existing = self.processes.get(task_id)
            if process is None or existing is process:
                self.processes.pop(task_id, None)

    def cancel_task(self, task_id, reason="用户手动终止任务"):
        process = None
        with self.lock:
            task = self.active_tasks.get(task_id)
            if task is None:
                return None
            if task.get("terminalStatus"):
                return dict(task)
            task["cancelRequested"] = True
            task["status"] = "正在取消"
            task["message"] = reason
            self.cancelled_task_ids.add(task_id)
            process = self.processes.get(task_id)

        self._terminate_process(process)
        self.complete_task(task_id, "cancelled", reason, error=reason)
        with self.lock:
            return dict(self.active_tasks.get(task_id) or self.task_results.get(task_id) or {})

    @staticmethod
    def _terminate_process(process):
        if process is None:
            return
        try:
            if process.poll() is None:
                process.terminate()
        except Exception:
            pass

        deadline = time.time() + 2.0
        while time.time() < deadline:
            try:
                if process.poll() is not None:
                    return
            except Exception:
                return
            time.sleep(0.05)

        try:
            if process.poll() is None:
                process.kill()
        except Exception:
            pass

    def is_cancel_requested(self, task_id):
        if not task_id:
            return False
        with self.lock:
            task = self.active_tasks.get(task_id)
            return task_id in self.cancelled_task_ids or bool(task and task.get("cancelRequested"))

    def raise_if_cancelled(self, task_id):
        if self.is_cancel_requested(task_id):
            raise TaskCancelledError("任务已被用户手动终止")

    def get_active_tasks_list(self):
        with self.lock:
            tasks = [dict(task) for task in self.active_tasks.values()]
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
                for filename in task.get("cleanupFiles") or []:
                    if filename:
                        referenced.add(filename)
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
            self.task_events.pop(task_id, None)
            self.task_results.pop(task_id, None)
            self.processes.pop(task_id, None)


# global singleton
task_manager = TaskManager()
