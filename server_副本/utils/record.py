## server.py v3.0.36
# guaguastandup
# zotero-pdf2zh
from threading import Lock
import datetime

# 合并翻译记录和进度条目
# 文件名 | 状态 | 进度 | 文件大小
# TODO: 目前进度同步逻辑还没有完成

class RecordTracker:
    def __init__(self):
        self.records = []   # 翻译记录条目
        self.progress = {}  # 翻译条目对应的进度
        self.records_lock = Lock()
        self.progress_lock = Lock()

    # 当翻译指令到达时, 新增翻译记录
    def add_record(self, filename, status, config_data, error_message=None): 
        with self.records_lock:
            record = {
                'id': len(self.records) + 1,
                'filename': filename,
                'status': status,
                'timestamp': datetime.datetime.now().isoformat(),
                'config': config_data,
                'error_message': error_message
            }
            self.records.append(record)
            return record

    def update_record(self, record_id, status, progress, error_message=None):
        with self.records_lock:
            for record in self.records:
                if record['id'] == record_id:
                    record['status'] = status               # 更新翻译状态
                    record['progress'] = progress           # 更新进度
                    record['error_message'] = error_message # 更新错误信息
                    record['updated_at'] = datetime.datetime.now().isoformat()
                    return record
        return None