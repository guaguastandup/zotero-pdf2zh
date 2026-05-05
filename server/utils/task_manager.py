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
        # Codex review #298 P1 round 11: NOT clearing _cancelled_tasks here.
        # Reason: when /api/abort kills a pdf2zh subprocess via SIGTERM, the
        # subprocess exits non-zero -> translate_pdf catches CalledProcessError
        # and retries with --skip-subset-fonts. If we cleared the cancel marker
        # at this point (the abort path also calls complete_task before the
        # retry runs), the retry would not see the cancellation and would
        # re-spawn another translation pass. Marker is now cleared elsewhere
        # (translate_pdf retry path checks marker; new task IDs are unique uuids
        # so stale markers between tasks don't interfere).
        with self.lock:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                # Codex review #298 P2 round 4: 幂等 — 已经 terminal 不重复写 history,
                # 防止 abort + worker finally 都调 complete_task 时产生重复 entry
                if task.get('active') is False:
                    return
                task["active"] = False
                task["status"] = "完成" if status == "success" else "失败"
                task["progress"] = 100 if status == "success" else task.get("progress", 0)
                if message:
                    task["message"] = message
                task["endTime"] = datetime.now().isoformat()

                history_item = {
                    "fileName": task.get("fileName"),
                    "status": "success" if status == "success" else "failed",
                    "engine": task.get("engine"),
                    "service": task.get("service"),
                    "startTime": task.get("startTime"),
                    "endTime": task.get("endTime"),
                    "config": task.get("config"),
                }
                if file_list:
                    history_item["fileList"] = list(file_list)
                if error:
                    history_item["error"] = str(error)

                self.progress_history.insert(0, history_item)
                if len(self.progress_history) > 200:
                    self.progress_history = self.progress_history[:200]

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
        with self.lock:
            return list(self.progress_history)

    def _delayed_remove(self, task_id):
        time.sleep(30)
        with self.lock:
            if task_id in self.active_tasks:
                # _debug_progress_log("TASK_REMOVE", task_id=task_id)
                del self.active_tasks[task_id]


# global singleton
task_manager = TaskManager()
