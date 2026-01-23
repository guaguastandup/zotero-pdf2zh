import uuid
import threading
import time
from enum import Enum
from typing import Dict, Any, Optional, Callable
from datetime import datetime, timedelta

class TaskStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Task:
    def __init__(self, task_id: str, task_type: str, data: Dict[str, Any]):
        self.task_id = task_id
        self.task_type = task_type
        self.data = data
        self.status = TaskStatus.PENDING
        self.result = None
        self.error = None
        self.progress = 0
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
        self.completed_at = None

    def to_dict(self):
        return {
            'task_id': self.task_id,
            'task_type': self.task_type,
            'status': self.status.value,
            'result': self.result,
            'error': self.error,
            'progress': self.progress,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }

class TaskManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(TaskManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.tasks: Dict[str, Task] = {}
        self.tasks_lock = threading.Lock()
        # 启动清理线程
        self._start_cleanup_thread()

    def create_task(self, task_type: str, data: Dict[str, Any]) -> str:
        """创建新任务并返回任务ID"""
        task_id = str(uuid.uuid4())
        task = Task(task_id, task_type, data)

        with self.tasks_lock:
            self.tasks[task_id] = task

        print(f"📝 [TaskManager] 创建任务: {task_id}, 类型: {task_type}")
        return task_id

    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务信息"""
        with self.tasks_lock:
            return self.tasks.get(task_id)

    def update_task_status(self, task_id: str, status: TaskStatus,
                          result: Any = None, error: str = None, progress: int = None):
        """更新任务状态"""
        with self.tasks_lock:
            task = self.tasks.get(task_id)
            if task:
                task.status = status
                task.updated_at = datetime.now()

                if result is not None:
                    task.result = result
                if error is not None:
                    task.error = error
                if progress is not None:
                    task.progress = progress
                if status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                    task.completed_at = datetime.now()

                print(f"🔄 [TaskManager] 更新任务 {task_id}: {status.value}, 进度: {task.progress}%")

    def execute_task(self, task_id: str, func: Callable, *args, **kwargs):
        """在后台线程中执行任务"""
        def worker():
            try:
                self.update_task_status(task_id, TaskStatus.PROCESSING, progress=0)
                result = func(*args, **kwargs)
                self.update_task_status(task_id, TaskStatus.COMPLETED, result=result, progress=100)
            except Exception as e:
                error_msg = str(e)
                print(f"❌ [TaskManager] 任务 {task_id} 失败: {error_msg}")
                self.update_task_status(task_id, TaskStatus.FAILED, error=error_msg, progress=0)

        thread = threading.Thread(target=worker, daemon=True)
        thread.start()

    def delete_task(self, task_id: str):
        """删除任务"""
        with self.tasks_lock:
            if task_id in self.tasks:
                del self.tasks[task_id]
                print(f"🗑️ [TaskManager] 删除任务: {task_id}")

    def _cleanup_old_tasks(self):
        """清理超过1小时的已完成任务"""
        while True:
            try:
                time.sleep(300)  # 每5分钟检查一次
                cutoff_time = datetime.now() - timedelta(hours=1)

                with self.tasks_lock:
                    tasks_to_delete = []
                    for task_id, task in self.tasks.items():
                        if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                            if task.completed_at and task.completed_at < cutoff_time:
                                tasks_to_delete.append(task_id)

                    for task_id in tasks_to_delete:
                        del self.tasks[task_id]

                    if tasks_to_delete:
                        print(f"🧹 [TaskManager] 清理了 {len(tasks_to_delete)} 个过期任务")
            except Exception as e:
                print(f"⚠️ [TaskManager] 清理任务时出错: {e}")

    def _start_cleanup_thread(self):
        """启动清理线程"""
        cleanup_thread = threading.Thread(target=self._cleanup_old_tasks, daemon=True)
        cleanup_thread.start()
