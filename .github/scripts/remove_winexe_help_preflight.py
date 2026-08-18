from pathlib import Path

path = Path('server/server.py')
text = path.read_text(encoding='utf-8')
start_marker = '                # 23秒可见性预检\n'
end_marker = '                # 执行主命令 - 附着父控制台\n'
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit('winexe visibility preflight block not found')
replacement = '''                # Do not launch a separate ``--help`` process just to probe
                # console visibility.  Some standalone pdf2zh executables do
                # substantial initialization even for help output.  The real
                # translation process below is the only process needed here;
                # DeepSeek capability validation remains handled separately.
'''
text = text[:start] + replacement + text[end:]
path.write_text(text, encoding='utf-8')
print('removed winexe help visibility preflight')
