"""Local object-storage mock: public files only, no data API or SPA fallback."""
import argparse
import os
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from http_files import FileHandler, REPOSITORY_ROOT


class ResourceHandler(FileHandler):
    def do_GET(self):
        self.serve(False)

    def do_HEAD(self):
        self.serve(True)

    def serve(self, head):
        path = self.request_path()
        if path is None:
            return
        if path == '/health':
            self.serve_json({'ok': True, 'service': 'visualbench-resources', 'time': datetime.now(timezone.utc).isoformat()}, head)
        else:
            self.serve_resource(path, head)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=4180)
    parser.add_argument('--root', type=Path, default=Path(os.environ.get('VISUALBENCH_RESOURCE_ROOT', REPOSITORY_ROOT)))
    parser.add_argument('--cache-seconds', type=int, default=60)
    args = parser.parse_args()
    if args.cache_seconds < 0:
        parser.error('--cache-seconds must be nonnegative')
    ResourceHandler.root = args.root.resolve()
    ResourceHandler.resource_cache_seconds = args.cache_seconds
    print(f'资源服务 http://{args.host}:{args.port} · root={ResourceHandler.root}', flush=True)
    ThreadingHTTPServer((args.host, args.port), ResourceHandler).serve_forever()
