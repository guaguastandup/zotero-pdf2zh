# task_manager.py
# 简化版任务管理器 - 仅提供 index.html 前端进度显示所需的最小功能
# 不包含终端日志美化功能（日志显示保持原有方式不变）
#
# 功能说明:
# - 跟踪当前活动的翻译任务（供 SSE /events 端点推送给前端）
# - 记录翻译历史（供 /api/history 端点返回给前端）
# - 任务完成后延迟30秒移除，给前端留出显示"完成状态"的时间

import threading
import time
from datetime import datetime


class TaskManager:
    """
    简化版任务管理器
    仅提供 index.html 前端进度显示所需的数据管理功能：
    - 跟踪活动翻译任务
    - 记录翻译历史
    - 为 SSE (/events) 和历史 API (/api/history) 提供数据
    """
    def __init__(self):
        self.active_tasks = {}       # key: task_id, value: task info dict
        self.lock = threading.Lock()
        # Web UI /api/history 使用的历史记录
        # item 结构: {fileName, status, engine, service, startTime, endTime, fileList?, error?}
        self.progress_history = []

    def add_task(self, task_id, info):
        """添加一个新的活动任务"""
        with self.lock:
            self.active_tasks[task_id] = info

    def update_task(self, task_id, updates):
        """更新任务信息（如进度百分比、状态文本等）"""
        with self.lock:
            if task_id in self.active_tasks:
                self.active_tasks[task_id].update(updates)

    def complete_task(self, task_id, status, message=None, file_list=None, error=None):
        """
        标记任务完成(成功或失败)并记录到历史
        参数:
            task_id: 任务唯一标识
            status: 'success' 或 'failed'
            message: 完成信息
            file_list: 生成的文件列表（成功时）
            error: 错误信息（失败时）
        """
        with self.lock:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                task['active'] = False
                task['status'] = '完成' if status == 'success' else '失败'
                task['progress'] = 100 if status == 'success' else task.get('progress', 0)
                if message:
                    task['message'] = message
                task['endTime'] = datetime.now().isoformat()

                # 写入历史记录（供 /api/history 与 index.html 使用）
                history_item = {
                    'fileName': task.get('fileName'),
                    'status': 'success' if status == 'success' else 'failed',
                    'engine': task.get('engine'),
                    'service': task.get('service'),
                    'startTime': task.get('startTime'),
                    'endTime': task.get('endTime'),
                }
                if file_list:
                    history_item['fileList'] = list(file_list)
                if error:
                    history_item['error'] = str(error)

                self.progress_history.insert(0, history_item)
                # 防止历史无限增长：只保留最近 200 条
                if len(self.progress_history) > 200:
                    self.progress_history = self.progress_history[:200]

                # 延迟移除已完成任务（给前端留显示时间）
                threading.Thread(
                    target=self._delayed_remove, args=(task_id,), daemon=True
                ).start()

    def get_active_tasks_list(self):
        """获取所有活动任务列表（供 SSE /events 端点使用）"""
        with self.lock:
            return list(self.active_tasks.values())

    def get_history(self):
        """获取历史记录列表（供 /api/history 端点使用）"""
        with self.lock:
            return list(self.progress_history)

    def _delayed_remove(self, task_id):
        """延迟30秒后移除已完成的任务，给前端留出显示完成状态的窗口"""
        time.sleep(30)
        with self.lock:
            if task_id in self.active_tasks:
                del self.active_tasks[task_id]


# 全局单例实例
task_manager = TaskManager()
