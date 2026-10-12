"""Local gallery and isolated-origin artifact file server. Never serves raw pi sessions."""
import argparse
import mimetypes
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit
from common import ROOT, PACKS

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        self.serve(False)

    def do_HEAD(self):
        self.serve(True)

    def serve(self, head):
        url = unquote(urlsplit(self.path).path)
        if '\x00' in url or '..' in url.split('/'):
            self.send_error(403); return
        if url.startswith('/data/'):
            path = ROOT / url.lstrip('/')
            allowed_root = ROOT / 'data'
        elif url == '/results/index.json':
            path = ROOT / 'results/index.json'
            allowed_root = ROOT / 'results'
        elif url.startswith('/results/runs/'):
            path = ROOT / url[len('/results/'):]
            if any(part in {'private', 'node_modules', '.git', '.pi'} for part in path.parts) or path.suffix == '.log' or (path.suffix == '.jsonl' and 'trajectory' not in path.parts):
                self.send_error(403); return
            bits = path.relative_to(ROOT/'runs').parts
            if len(bits) < 5:
                self.send_error(403); return
            allowed_root = ROOT/'runs'/Path(*bits[:4])
            if any((ROOT/'runs'/Path(*bits[:i])).is_symlink() for i in range(1,5)):
                self.send_error(403); return
        elif url.startswith('/inputs/'):
            bits = url.split('/', 3)
            if len(bits) < 4 or bits[2] not in PACKS:
                self.send_error(404); return
            path = PACKS[bits[2]] / bits[3]
            allowed_root = PACKS[bits[2]]
        else:
            path = ROOT / 'app/dist' / (url.lstrip('/') or 'index.html')
            if not path.is_file() and '.' not in path.name:
                path = ROOT / 'app/dist/index.html'
            allowed_root = ROOT / 'app/dist'
        resolved = path.resolve()
        if not resolved.is_relative_to(ROOT) or any(part in {'private','node_modules','.git','.pi'} for part in resolved.relative_to(ROOT).parts):
            self.send_error(403); return
        if resolved.suffix == '.log' or (resolved.suffix == '.jsonl' and 'trajectory' not in resolved.parts):
            self.send_error(403); return
        if not path.is_file() or not resolved.is_relative_to(allowed_root.resolve()):
            self.send_error(404); return
        size = path.stat().st_size
        start, end, partial = 0, size - 1, False
        match = re.fullmatch(r'bytes=(\d+)-(\d*)', self.headers.get('Range', ''))
        if match:
            start = int(match[1]); end = min(int(match[2]) if match[2] else end, end); partial = True
            if start > end:
                self.send_error(416); return
        self.send_response(206 if partial else 200)
        self.send_header('Content-Type', mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
        self.send_header('Content-Length', str(max(0, end - start + 1)))
        self.send_header('Accept-Ranges', 'bytes')
        if partial: self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.send_header('Cache-Control', 'no-store' if path.suffix == '.json' else 'max-age=60')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('X-Content-Type-Options', 'nosniff')
        if path.suffix == '.jsonl':
            identity = '-'.join(path.relative_to(ROOT/'runs').parts[:4]) if path.is_relative_to(ROOT/'runs') else 'visualbench'
            identity = re.sub(r'[^a-zA-Z0-9_.-]', '-', identity)
            self.send_header('Content-Disposition', f'attachment; filename="{identity}-{path.name}"')
        if path.suffix == '.html' and '/results/runs/' in url and 'trajectory' not in path.parts:
            self.send_header('Content-Security-Policy', "default-src 'self' data: blob:; script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-src 'none'; object-src 'none'")
        self.end_headers()
        if not head:
            try:
                with path.open('rb') as f:
                    f.seek(start); remaining = end-start+1
                    while remaining > 0:
                        b = f.read(min(1024*1024, remaining))
                        if not b: break
                        self.wfile.write(b); remaining -= len(b)
            except (BrokenPipeError, ConnectionResetError): pass

    def log_message(self, fmt, *args):
        if args and str(args[1]) not in {'200', '206', '304'}:
            super().log_message(fmt, *args)

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--port', type=int, default=4174); a = p.parse_args()
    print(f'VisualBench data / preview server: http://127.0.0.1:{a.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', a.port), Handler).serve_forever()
