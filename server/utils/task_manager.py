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
        # 停止回调旁路注册表: 任务信息要保持可 JSON 序列化, 运行时句柄放这里。
        self._stoppers = {}
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

    def get_task(self, task_id):
        with self.lock:
            task = self.active_tasks.get(task_id)
            return dict(task) if task else None

    def register_stopper(self, task_id, stopper):
        """注册任务的可选停止回调(wenyi 共享运行时的 close)。"""
        if callable(stopper):
            with self.lock:
                self._stoppers[task_id] = stopper


    def cancel_task(self, task_id, message='Cancelled by user'):
        """标记任务取消并触发注册的停止回调。

        wenyi 的 CLI 子进程已按任务独立(wenyi.cancel_task 只终止目标
        任务的进程), 因此只取消目标任务本身; 共享 bridge 时代"停一个
        等于停全部"的连带取消已随之移除。
        """
        with self.lock:
            task = self.active_tasks.get(task_id)
            if not task or task.get('finished'):
                return False
            stopper = self._stoppers.get(task_id)
        if callable(stopper):
            try:
                stopper()
            except Exception as exc:
                print(f"⚠️ 停止任务 {task_id} 的运行时失败: {exc}")
        self.complete_task(task_id, 'cancelled', message=message)
        return True
                # _debug_progress_log(
                #     "TASK_UPDATE",
                #     updates=json.dumps(updates, ensure_ascii=False, sort_keys=True),
                #     task=self._task_snapshot(task_id, self.active_tasks[task_id]),
                # )

    def complete_task(self, task_id, status, message=None, file_list=None, error=None, file_paths=None, output_dir=None, result=None):
        with self.lock:
            if task_id not in self.active_tasks:
                # 任务从未入表(如请求校验 400 早退): 仍要清掉旁路注册表,
                # 否则持有运行时引用的 stopper 闭包会一直泄漏。
                self._stoppers.pop(task_id, None)
                return
            task = self.active_tasks[task_id]
            # Client disconnect after a successful translate can raise while
            # returning HTTP. A finished task (完成/已取消) is final: never
            # overwrite it (e.g. cancelled → failed after the killed CLI
            # process exits non-zero) and never duplicate its history entry.
            if task.get("finished"):
                return
            task["active"] = False
            task["finished"] = True
            task["status"] = (
                "已取消" if status == "cancelled"
                else "完成" if status == "success"
                else "失败"
            )
            task["progress"] = 100 if status == "success" else task.get("progress", 0)
            if message:
                task["message"] = message
            task["endTime"] = datetime.now().isoformat()
            if file_list:
                task["fileList"] = list(file_list)
            if file_paths:
                task["filePaths"] = list(file_paths)
            if output_dir:
                task["outputDir"] = output_dir
            if result:
                task["result"] = result
            if error:
                task["error"] = str(error)

            self._stoppers.pop(task_id, None)
            history_item = {
                "taskId": task_id,
                "fileName": task.get("fileName"),
                "status": (
                    "cancelled" if status == "cancelled"
                    else "success" if status == "success"
                    else "failed"
                ),
                "finished": True,
                "active": False,
                "engine": task.get("engine"),
                "service": task.get("service"),
                "startTime": task.get("startTime"),
                "endTime": task.get("endTime"),
                "config": task.get("config"),
            }
            if file_list:
                history_item["fileList"] = list(file_list)
            if file_paths:
                history_item["filePaths"] = list(file_paths)
            if output_dir:
                history_item["outputDir"] = output_dir
            if result:
                history_item["result"] = result
            if error:
                history_item["error"] = str(error)

            self.progress_history.insert(0, history_item)
            if len(self.progress_history) > 200:
                self.progress_history = self.progress_history[:200]

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
