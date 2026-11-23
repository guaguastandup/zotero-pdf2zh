import unittest
from utils.task_manager import TaskManager


class TaskLifecycleTests(unittest.TestCase):
    def manager(self):
        manager = TaskManager()
        manager._delayed_remove = lambda _id: None
        for tid in ('first', 'second'):
            manager.add_task(tid, dict(taskId=tid, active=True, finished=False,
                                      engine='wenyi', progress=20))
        return manager

    def test_cancelling_shared_runtime_keeps_all_tasks_cancelled_after_worker_errors(self):
        manager = self.manager()
        def stop():
            # Simulate workers reacting synchronously as the runtime stops.
            for tid in ('first', 'second'):
                manager.complete_task(tid, 'failed', error='runtime stopped')
                manager.update_task(tid, dict(status='running', progress=90))
        manager.register_stopper('first', stop)
        manager.register_stopper('second', stop)
        self.assertTrue(manager.cancel_task('first'))
        for tid in ('first', 'second'):
            task = manager.get_task(tid)
            self.assertEqual(task['status'], '已取消')
            self.assertEqual(task['progress'], 20)
            self.assertTrue(task['finished'])
        history = manager.get_history()
        self.assertEqual(len(history), 2)
        self.assertTrue(all(task['status'] == 'cancelled' for task in history))

    def test_late_success_does_not_resurrect_a_cancelled_task(self):
        manager = self.manager()
        manager.cancel_task('first')
        manager.complete_task('first', 'success', file_list=['late.pdf'])
        task = manager.get_task('first')
        self.assertEqual(task['status'], '已取消')
        self.assertNotIn('fileList', task)

    def test_duplicate_completion_does_not_create_duplicate_history(self):
        manager = self.manager()
        manager.complete_task('first', 'failed', error='first failure')
        manager.complete_task('first', 'failed', error='second failure')
        self.assertEqual(len(manager.get_history()), 1)
        self.assertEqual(manager.get_task('first')['error'], 'first failure')
