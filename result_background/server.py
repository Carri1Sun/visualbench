"""result_background: JSON API + artifact file server for result_display_frontend.

Serves three planes from the repository root:
  /api/*                          small JSON data endpoints (catalog, index, ...)
  /results/runs/**, /inputs/**    immutable run artifacts and frozen inputs (Range supported)
  /*                              built SPA from result_display_frontend/dist (optional, single-host mode)

Security rules (unchanged from the original bench server):
  - never serves raw pi sessions: `private/`, `.pi/`, `.git/`, node_modules are 403
  - `*.log` and non-trajectory `*.jsonl` are 403
  - path traversal and symlinked run roots are rejected
  - trajectory HTML gets a restrictive CSP; JSON is always no-store

This module is intentionally self-contained: deploying the gallery to a server
does not require run_control/ or any local pi configuration.
"""
import argparse
import json
import mimetypes
import re
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PACKS = {'frontend': ROOT / 'frontend-showcase-inputs-v1', 'video': ROOT / 'video-bench-inputs-v1'}
FRONTEND_DIST = ROOT / 'result_display_frontend' / 'dist'

# /api/* endpoints -> file on disk. All are read-only JSON documents
# produced by run_control; the background never generates them itself.
API_ROUTES = {
    '/api/catalog': ROOT / 'data/catalog.json',
    '/api/index': ROOT / 'results/index.json',
    '/api/trajectories': ROOT / 'data/trajectories.json',
    '/api/audits': ROOT / 'data/audits.json',
    '/api/execution-changes': ROOT / 'data/execution-changes.json',
    '/api/environment': ROOT / 'data/environment.json',
}


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        self.serve(False)

    def do_HEAD(self):
        self.serve(True)

    def serve(self, head):
        url = unquote(urlsplit(self.path).path)
        if '\x00' in url or '..' in url.split('/'):
            self.send_error(403); return
        if url == '/api/health':
            body = json.dumps({'ok': True, 'service': 'result_background', 'time': datetime.now(timezone.utc).isoformat()}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            if not head:
                try: self.wfile.write(body)
                except (BrokenPipeError, ConnectionResetError): pass
            return
        if url in API_ROUTES:
            self.serve_file(API_ROUTES[url], head)
            return
        if url.startswith('/api/'):
            self.send_error(404); return
        if url == '/results/index.json':
            self.serve_file(ROOT / 'results/index.json', head)
            return
        if url.startswith('/results/runs/'):
            path = ROOT / url[len('/results/'):]
            if any(part in {'private', 'node_modules', '.git', '.pi'} for part in path.parts) or path.suffix == '.log' or (path.suffix == '.jsonl' and 'trajectory' not in path.parts):
                self.send_error(403); return
            bits = path.relative_to(ROOT/'runs').parts
            if len(bits) < 5:
                self.send_error(403); return
            allowed_root = ROOT/'runs'/Path(*bits[:4])
            if any((ROOT/'runs'/Path(*bits[:i])).is_symlink() for i in range(1,5)):
                self.send_error(403); return
            self.serve_file(path, head, allowed_root=allowed_root, trajectory_root=(ROOT/'runs'))
            return
        if url.startswith('/inputs/'):
            bits = url.split('/', 3)
            if len(bits) < 4 or bits[2] not in PACKS:
                self.send_error(404); return
            path = PACKS[bits[2]] / bits[3]
            self.serve_file(path, head, allowed_root=PACKS[bits[2]])
            return
        path = FRONTEND_DIST / (url.lstrip('/') or 'index.html')
        if not path.is_file() and '.' not in path.name:
            path = FRONTEND_DIST / 'index.html'
        self.serve_file(path, head, allowed_root=FRONTEND_DIST)

    def serve_file(self, path, head, allowed_root=None, trajectory_root=None):
        if allowed_root is None:
            allowed_root = path.parent
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
        if path.suffix == '.jsonl' and trajectory_root is not None:
            identity = '-'.join(path.relative_to(trajectory_root).parts[:4])
            identity = re.sub(r'[^a-zA-Z0-9_.-]', '-', identity)
            self.send_header('Content-Disposition', f'attachment; filename="{identity}-{path.name}"')
        if path.suffix == '.html' and trajectory_root is not None and 'trajectory' not in path.parts:
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
    p = argparse.ArgumentParser(); p.add_argument('--port', type=int, default=4174); p.add_argument('--host', default='127.0.0.1'); a = p.parse_args()
    print(f'result_background API / artifact server: http://{a.host}:{a.port} (/api/health)', flush=True)
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()
