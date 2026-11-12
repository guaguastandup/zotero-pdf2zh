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

    def reactivate_task(self, task_id, status='续传中'):
        """把已结束的任务重新置为运行(断点续传复用原 workspace/taskId)。"""
        with self.lock:
            task = self.active_tasks.get(task_id)
            if not task:
                return False
            task.update({
                'active': True, 'finished': False,
                'status': status, 'progress': 0,
                'message': '正在续传...', 'endTime': None,
            })
            return True

    def cancel_task(self, task_id, message='Cancelled by user'):
        """标记任务取消并触发注册的停止回调(wenyi 运行时)。

        wenyi 的 BabelDOC bridge 是所有任务共享的单例, 停止它会终止全部
        运行中的 wenyi 任务, 因此这里把同引擎的其他活动任务一并标记取消,
        界面状态与实际执行保持一致。
        """
        with self.lock:
            task = self.active_tasks.get(task_id)
            if not task or task.get('finished'):
                return False
            engine = task.get('engine')
            stopper = task.get('stopper')
            siblings = [
                (tid, self._stoppers.get(tid)) for tid, info in self.active_tasks.items()
                if info.get('engine') == engine and not info.get('finished')
            ] if engine == 'wenyi' else [(task_id, self._stoppers.get(task_id))]
        stopped_ids = set()
        for _tid, sibling_stopper in siblings:
            if callable(sibling_stopper):
                stopper_key = id(sibling_stopper)
                if stopper_key not in stopped_ids:
                    stopped_ids.add(stopper_key)
                    try:
                        sibling_stopper()
                    except Exception as exc:
                        print(f"⚠️ 停止任务 {_tid} 的运行时失败: {exc}")
            self.complete_task(_tid, 'cancelled', message=message)
        return True
                # _debug_progress_log(
                #     "TASK_UPDATE",
                #     updates=json.dumps(updates, ensure_ascii=False, sort_keys=True),
                #     task=self._task_snapshot(task_id, self.active_tasks[task_id]),
                # )

    def complete_task(self, task_id, status, message=None, file_list=None, error=None, file_paths=None, output_dir=None, result=None):
        with self.lock:
            if task_id not in self.active_tasks:
                return
            task = self.active_tasks[task_id]
            # Client disconnect after a successful translate can raise while
            # returning HTTP; do not overwrite a completed success as failure.
            if task.get("active") is False and task.get("status") == "完成":
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
