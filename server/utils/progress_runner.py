"""Run the installed CLI with structured progress instead of Rich live tables."""
import contextlib
import json
import sys
import runpy

PREFIX = 'PDF2ZH_PROGRESS '


def create_progress_handler(_config, *args, **kwargs):
    def report(event):
        if event.get('type') not in {'progress_start', 'progress_update', 'progress_end', 'finish', 'error'}:
            return
        fields = ('type', 'stage', 'stage_current', 'stage_total', 'overall_progress', 'part_index', 'total_parts', 'error')
        payload = {key: event[key] for key in fields if key in event}
        print(PREFIX + json.dumps(payload, ensure_ascii=False), flush=True)
    return contextlib.nullcontext(), report


def main():
    import pdf2zh_next.high_level as high_level
    from pdf2zh_next.main import cli

    high_level.create_progress_handler = create_progress_handler
    if sys.argv[1:2] == ['--wrapped-script']:
        script = sys.argv[2]
        sys.argv = [script, *sys.argv[3:]]
        runpy.run_path(script, run_name='__main__')
    else:
        cli()


if __name__ == '__main__':
    main()
