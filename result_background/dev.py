"""Run only the display stack; never start evaluators or archive writers."""
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICES = [
    ('server', 4174, [sys.executable, '-u', 'result_background/server.py'], ROOT),
    ('resources', 4180, [sys.executable, '-u', 'result_background/resource_server.py'], ROOT),
    ('app', 4173, ['npm', 'run', 'dev'], ROOT / 'result_display_frontend'),
]


def main():
    for _, port, _, _ in SERVICES:
        with socket.socket() as probe:
            if probe.connect_ex(('127.0.0.1', port)) == 0:
                print(f'端口 {port} 已被占用，请先停止该端口的旧展示服务，再运行 npm run dev。', file=sys.stderr)
                return 1
    children = []
    pidfiles = []

    def stop(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop)
    try:
        (ROOT / '.runtime').mkdir(exist_ok=True)
        for name, _, command, cwd in SERVICES:
            child = subprocess.Popen(command, cwd=cwd, start_new_session=True)
            children.append(child)
            pidfile = ROOT / '.runtime' / f'{name}.pid'
            pidfile.write_text(str(child.pid))
            pidfiles.append((pidfile, child.pid))
        print('展示页 http://127.0.0.1:4173 · API :4174 · 资源 :4180', flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(0.2)
        return next(child.returncode or 1 for child in children if child.poll() is not None)
    except KeyboardInterrupt:
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        deadline = time.monotonic() + 5
        for child in children:
            try:
                child.wait(timeout=max(0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
        for pidfile, pid in pidfiles:
            if pidfile.exists() and pidfile.read_text() == str(pid):
                pidfile.unlink()


if __name__ == '__main__':
    sys.exit(main())
