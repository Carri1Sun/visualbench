"""Read-only JSON API and optional built SPA. Resources live on another origin."""
import argparse
import os
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from http_files import FileHandler, REPOSITORY_ROOT

API_FILES = {
    '/api/catalog': 'data/catalog.json',
    '/api/index': 'results/index.json',
    '/api/trajectories': 'data/trajectories.json',
    '/api/audits': 'data/audits.json',
    '/api/execution-changes': 'data/execution-changes.json',
    '/api/environment': 'data/environment.json',
}


def resource_base_url(value):
    if value == '':
        return value
    parsed = urlsplit(value)
    if parsed.scheme not in {'http', 'https'} or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment or any(c.isspace() or c == '\\' for c in value):
        raise ValueError('resource base must be an HTTP(S) URL without credentials, query or fragment')
    return value.rstrip('/')


class Handler(FileHandler):
    resource_base = 'http://127.0.0.1:4180'
    with_resources = False
    sandbox_html = False

    def do_GET(self):
        self.serve(False)

    def do_HEAD(self):
        self.serve(True)

    def serve(self, head):
        url = self.request_path()
        if url is None:
            return
        if url == '/api/health':
            self.serve_json({'ok': True, 'service': 'result_background', 'time': datetime.now(timezone.utc).isoformat()}, head)
        elif url == '/api/config':
            self.serve_json({'resource_base_url': self.resource_base}, head)
        elif url in API_FILES:
            self.serve_file(self.root / API_FILES[url], head)
        elif url.startswith('/api/'):
            self.send_error(404)
        elif url.startswith(('/results/', '/inputs/')):
            if self.with_resources:
                self.serve_resource(url, head)
            else:
                self.send_error(404)
        else:
            dist = self.root / 'result_display_frontend/dist'
            path = dist / (url.lstrip('/') or 'index.html')
            if not path.is_file() and '.' not in path.name:
                path = dist / 'index.html'
            self.serve_file(path, head, allowed_root=dist)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=4174)
    parser.add_argument('--root', type=Path, default=Path(os.environ.get('VISUALBENCH_DATA_ROOT', REPOSITORY_ROOT)))
    parser.add_argument('--resource-base-url', type=resource_base_url, default=os.environ.get('VISUALBENCH_RESOURCE_BASE_URL', 'http://127.0.0.1:4180'))
    parser.add_argument('--with-resources', action='store_true', help='Compatibility mode for local evaluation capture')
    args = parser.parse_args()
    Handler.root = args.root.resolve()
    Handler.resource_base = resource_base_url(args.resource_base_url)
    Handler.with_resources = args.with_resources
    print(f'数据服务 http://{args.host}:{args.port} · resources={Handler.resource_base}', flush=True)
    ThreadingHTTPServer((args.host, args.port), Handler).serve_forever()
