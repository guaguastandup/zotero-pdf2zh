"""Isolate uploads/engine outputs, then publish immutable flat download names."""
from pathlib import Path
import os
import shutil
import tempfile
from uuid import uuid4


class JobFiles:
    def __init__(self, output_root, input_name):
        self.input_name = input_name
        self.output_root = Path(output_root).resolve()
        self.output_root.mkdir(parents=True, exist_ok=True)
        self.directory = Path(tempfile.mkdtemp(prefix='.job-', dir=self.output_root))
        self.token = uuid4().hex
        self._published = {}

    def publish(self, paths):
        published = []
        for raw in paths:
            source = Path(raw).resolve()
            if source.parent != self.directory.resolve():
                raise ValueError('任务结果文件不在本次任务目录中。')
            if source in self._published:
                published.append(self._published[source])
                continue
            # Keep the product suffix intact, including on long Unicode names.
            leaf = source.name.encode('utf-8')[-220:].decode('utf-8', errors='ignore')
            destination = self.output_root / f'{self.token}.{leaf}'
            # Both locations are on the same filesystem. Moving after the
            # engine exits is atomic and does not duplicate large PDFs on disk.
            os.replace(source, destination)
            self._published[source] = str(destination)
            published.append(str(destination))
        return published

    def preserve_outputs(self, save_glossary=False):
        # Keep generated PDFs for recovery even when later post-processing
        # fails. Never publish the uploaded source as a translated result.
        paths = [path for path in self.directory.iterdir()
                 if path.is_file() and path.name != self.input_name
                 and (path.suffix.lower() == '.pdf'
                      or (save_glossary and path.name.endswith('.glossary.csv')))]
        self.publish(paths)

    def cleanup(self):
        try:
            shutil.rmtree(self.directory)
        except FileNotFoundError:
            pass
