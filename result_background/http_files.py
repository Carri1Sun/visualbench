"""Shared read-only HTTP file transport for local API and resource services."""
import json
import mimetypes
import os
import re
from email.utils import formatdate
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlsplit

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {'private', 'node_modules', '.git', '.pi'}
HTML_CSP = ("default-src 'self' data: blob:; script-src 'self' 'unsafe-inline' 'unsafe-eval' blob:; "
            "style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-src 'none'; "
            "object-src 'none'; base-uri 'none'; form-action 'none'")


class FileHandler(SimpleHTTPRequestHandler):
    root = REPOSITORY_ROOT
    sandbox_html = True
    resource_cache_seconds = 60

    def end_headers(self):
        # Public read-only resources are readable from the app and opaque iframes.
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Expose-Headers', 'Content-Disposition, Content-Length, Content-Range, Accept-Ranges, ETag, Last-Modified')
        self.send_header('X-Content-Type-Options', 'nosniff')
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header('Access-Control-Allow-Methods', 'GET, HEAD, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Range, If-None-Match, If-Modified-Since, If-Range')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def request_path(self):
        raw = urlsplit(self.path).path
        try:
            path = unquote(raw, errors='strict')
        except (UnicodeError, ValueError):
            self.send_error(403)
            return None
        if re.search(r'%[0-9a-f]{2}', path, re.I) or re.search(r'[\x00-\x1f\x7f\\]', path) or '..' in path.split('/') or '.' in path.split('/') or '//' in path:
            self.send_error(403)
            return None
        return path

    def serve_json(self, value, head=False):
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        if not head:
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass

    def serve_resource(self, url, head=False):
        if url.startswith('/results/runs/'):
            relative = Path(url[len('/results/'):])
            bits = relative.parts[1:]
            if len(bits) < 5:
                self.send_error(403)
                return
            allowed = self.root / 'runs' / Path(*bits[:4])
            self.serve_file(self.root / relative, head, allowed_root=allowed, resource=True)
        elif url.startswith('/inputs/'):
            bits = url.split('/', 3)
            packs = {'frontend': 'frontend-showcase-inputs-v1', 'video': 'video-bench-inputs-v1'}
            if len(bits) < 4 or bits[2] not in packs:
                self.send_error(404)
                return
            allowed = self.root / packs[bits[2]]
            self.serve_file(allowed / bits[3], head, allowed_root=allowed, resource=True)
        else:
            self.send_error(404)

    def serve_file(self, path, head=False, allowed_root=None, resource=False):
        root = self.root.resolve()
        allowed = (allowed_root or path.parent).resolve()
        # macOS may spell the same root as /var/... and /private/var/....
        try:
            path = root / path.relative_to(self.root)
        except ValueError:
            self.send_error(403)
            return
        resolved = path.resolve()
        if not resolved.is_relative_to(root) or not resolved.is_relative_to(allowed):
            self.send_error(403)
            return
        parts = path.relative_to(root).parts
        if any(part in FORBIDDEN or part.startswith('.') for part in parts) or resolved.suffix == '.log' or (resolved.suffix == '.jsonl' and 'trajectory' not in parts):
            self.send_error(403)
            return
        # Do not follow symlinks, even when their target stays in the repository.
        if any((root / Path(*parts[:i])).is_symlink() for i in range(1, len(parts) + 1)):
            self.send_error(403)
            return
        if path.is_dir():
            self.serve_file(path / 'index.html', head, allowed, resource)
            return
        try:
            stream = path.open('rb')
        except (FileNotFoundError, IsADirectoryError, PermissionError):
            self.send_error(404)
            return
        with stream:
            stat = os.fstat(stream.fileno())
            size = stat.st_size
            etag = f'"{stat.st_mtime_ns:x}-{size:x}"'
            modified = formatdate(stat.st_mtime, usegmt=True)
            cache = f'public, max-age={self.resource_cache_seconds}' if resource else 'no-store'
            if resource and self.headers.get('If-None-Match') in {etag, '*'}:
                self.send_response(304)
                self.send_header('ETag', etag)
                self.send_header('Cache-Control', cache)
                self.end_headers()
                return
            start, end, partial = 0, size - 1, False
            range_header = '' if head else self.headers.get('Range', '')
            if self.headers.get('If-Range', etag) not in {etag, modified}:
                range_header = ''
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', range_header)
            if match and any(match.groups()):
                left, right = match.groups()
                if left:
                    start = int(left)
                    end = min(int(right), size - 1) if right else size - 1
                else:
                    start = max(0, size - int(right))
                if size == 0 or start > end or start >= size:
                    self.send_response(416)
                    self.send_header('Content-Range', f'bytes */{size}')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return
                partial = True
            self.send_response(206 if partial else 200)
            self.send_header('Content-Type', mimetypes.guess_type(path.name)[0] or 'application/octet-stream')
            self.send_header('Content-Length', str(max(0, end - start + 1)))
            self.send_header('Accept-Ranges', 'bytes')
            if partial:
                self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
            self.send_header('Cache-Control', cache)
            self.send_header('ETag', etag)
            self.send_header('Last-Modified', modified)
            query = parse_qs(urlsplit(self.path).query)
            if resource and (query.get('download') == ['1'] or path.suffix == '.jsonl'):
                filename = query.get('filename', [path.name])[0][:200]
                filename = re.sub(r'[\x00-\x1f\x7f/\\]', '-', filename)
                fallback = re.sub(r'[^a-zA-Z0-9_.-]', '-', filename) or 'download'
                self.send_header('Content-Disposition', f'attachment; filename="{fallback}"; filename*=UTF-8\'\'{quote(filename, safe="")}')
            if resource and path.suffix in {'.html', '.htm'}:
                csp = HTML_CSP
                if self.sandbox_html:
                    csp = 'sandbox allow-scripts; ' + csp
                if self.sandbox_html or 'trajectory' not in parts:
                    self.send_header('Content-Security-Policy', csp)
            self.end_headers()
            if not head:
                try:
                    stream.seek(start)
                    remaining = end - start + 1
                    while remaining > 0:
                        chunk = stream.read(min(1024 * 1024, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    pass

    def log_message(self, fmt, *args):
        if len(args) < 2 or str(args[1]) not in {'200', '206', '304'}:
            super().log_message(fmt, *args)
