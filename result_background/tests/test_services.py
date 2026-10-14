"""Exercise real HTTP transports with temporary objects, never benchmark files."""
import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from resource_server import ResourceHandler
from server import Handler, resource_base_url


class ServicesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.prefix = '/results/runs/frontend/model/task/run-1/'
        self.run = self.root / self.prefix.removeprefix('/results/')
        (self.run / 'work/assets').mkdir(parents=True)
        (self.run / 'trajectory').mkdir()
        (self.run / 'private').mkdir()
        (self.run / 'work/video.mp4').write_bytes(b'0123456789')
        (self.run / 'work/artifact.html').write_text('<html><img src="assets/poster.png"><button>测试</button></html>')
        (self.run / 'work/assets/poster.png').write_bytes(b'png-fixture')
        (self.run / 'work/project.zip').write_bytes(b'zip-fixture')
        (self.run / 'trajectory/session.html').write_text('<html>轨迹</html>')
        (self.run / 'trajectory/session.jsonl').write_bytes(b'{"message":"fixture"}\n')
        (self.run / 'private/session.jsonl').write_bytes(b'private')
        (self.run / 'work/debug.log').write_bytes(b'private-log')
        (self.root / 'data').mkdir()
        (self.root / 'data/catalog.json').write_text('{"cases":[],"models":[]}')
        (self.root / 'results').mkdir()
        (self.root / 'results/index.json').write_text('{"runs":[]}')
        (self.root / 'frontend-showcase-inputs-v1/assets').mkdir(parents=True)
        (self.root / 'frontend-showcase-inputs-v1/assets/input.png').write_bytes(b'input')
        self.servers = []
        self.resources = self.start(type('TestResources', (ResourceHandler,), {'root': self.root}))
        self.api = self.start(type('TestAPI', (Handler,), {'root': self.root, 'resource_base': self.resources}))

    def start(self, handler):
        server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.servers.append((server, thread))
        return f'http://127.0.0.1:{server.server_port}'

    def tearDown(self):
        for server, thread in self.servers:
            server.shutdown()
            server.server_close()
            thread.join()
        self.temp.cleanup()

    def request(self, base, path, headers=None, method='GET'):
        try:
            response = urlopen(Request(base + path, headers=headers or {}, method=method), timeout=5)
        except HTTPError as error:
            response = error
        with response:
            return response.code, response.headers, response.read()

    def test_api_returns_configuration_and_metadata_without_serving_objects(self):
        code, _, body = self.request(self.api, '/api/config')
        self.assertEqual(code, 200)
        self.assertEqual(json.loads(body)['resource_base_url'], self.resources)
        code, headers, body = self.request(self.api, '/api/catalog')
        self.assertEqual(json.loads(body), {'cases': [], 'models': []})
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(self.request(self.api, self.prefix + 'work/video.mp4')[0], 404)
        self.assertEqual(self.request(self.resources, '/api/catalog')[0], 404)
        self.assertEqual(self.request(self.resources, '/')[0], 404)

    def test_resources_are_cross_origin_readable_with_relative_preview_assets(self):
        for path in ['work/artifact.html', 'work/assets/poster.png', 'trajectory/session.html', 'work/project.zip']:
            code, headers, _ = self.request(self.resources, self.prefix + path, {'Origin': 'http://127.0.0.1:4173'})
            self.assertEqual(code, 200)
            self.assertEqual(headers['Access-Control-Allow-Origin'], '*')
            self.assertEqual(headers['X-Content-Type-Options'], 'nosniff')
            if path.endswith('.html'):
                self.assertIn('sandbox allow-scripts;', headers['Content-Security-Policy'])
        code, _, body = self.request(self.resources, '/inputs/frontend/assets/input.png')
        self.assertEqual((code, body), (200, b'input'))
        code, headers, body = self.request(self.resources, self.prefix + 'work/video.mp4', method='OPTIONS')
        self.assertEqual((code, body), (204, b''))
        self.assertIn('Range', headers['Access-Control-Allow-Headers'])

    def test_video_seek_ranges_suffixes_and_stale_if_range(self):
        path = self.prefix + 'work/video.mp4'
        for value, expected, content_range in [('bytes=2-5', b'2345', 'bytes 2-5/10'), ('bytes=7-', b'789', 'bytes 7-9/10'), ('bytes=-3', b'789', 'bytes 7-9/10')]:
            code, headers, body = self.request(self.resources, path, {'Range': value})
            self.assertEqual((code, body), (206, expected))
            self.assertEqual(headers['Content-Range'], content_range)
        code, headers, body = self.request(self.resources, path, {'Range': 'bytes=50-'})
        self.assertEqual((code, body), (416, b''))
        self.assertEqual(headers['Content-Range'], 'bytes */10')
        self.assertEqual(self.request(self.resources, path, {'Range': 'bytes=2-4', 'If-Range': '"old"'})[2], b'0123456789')
        code, headers, body = self.request(self.resources, path, {'Range': 'bytes=2-4'}, method='HEAD')
        self.assertEqual((code, body, headers['Content-Length']), (200, b'', '10'))

    def test_cache_validates_changed_objects_and_keeps_api_uncached(self):
        path = self.prefix + 'work/video.mp4'
        _, headers, _ = self.request(self.resources, path)
        self.assertEqual(headers['Cache-Control'], 'public, max-age=60')
        etag = headers['ETag']
        self.assertEqual(self.request(self.resources, path, {'If-None-Match': etag})[0], 304)
        (self.run / 'work/video.mp4').write_bytes(b'new-video-content')
        code, headers, body = self.request(self.resources, path, {'If-None-Match': etag})
        self.assertEqual((code, body), (200, b'new-video-content'))
        self.assertNotEqual(headers['ETag'], etag)
        self.assertEqual(self.request(self.api, '/api/catalog', {'If-None-Match': '*'})[0], 200)

    def test_download_attachment_and_preview_are_separate(self):
        path = self.prefix + 'trajectory/session.html'
        self.assertIsNone(self.request(self.resources, path)[1].get('Content-Disposition'))
        code, headers, _ = self.request(self.resources, path + '?download=1&filename=%E8%BD%A8%E8%BF%B9.html')
        self.assertEqual(code, 200)
        self.assertIn('attachment;', headers['Content-Disposition'])
        self.assertIn("filename*=UTF-8''%E8%BD%A8%E8%BF%B9.html", headers['Content-Disposition'])
        self.assertIn('Content-Disposition', headers['Access-Control-Expose-Headers'])
        self.assertIn('attachment', self.request(self.resources, self.prefix + 'trajectory/session.jsonl')[1]['Content-Disposition'])
        self.assertIn('attachment', self.request(self.resources, self.prefix + 'work/project.zip?download=1')[1]['Content-Disposition'])

    def test_private_files_traversal_symlinks_and_missing_objects(self):
        (self.run / 'work/escape.txt').symlink_to(self.root / 'data/catalog.json')
        for tail in ['private/session.jsonl', 'work/debug.log', 'work/.env', 'work/escape.txt', 'work/../private/session.jsonl', 'work/%2e%2e/private/session.jsonl', 'work/%252e%252e/private/session.jsonl', 'work/%00x', 'work/node_modules/file.js']:
            self.assertEqual(self.request(self.resources, self.prefix + tail)[0], 403, tail)
        self.assertEqual(self.request(self.resources, self.prefix + 'work/missing.png')[0], 404)
        self.assertEqual(self.request(self.resources, '/results/runs/')[0], 403)

    def test_capture_compatibility_remains_explicit(self):
        capture = self.start(type('Capture', (Handler,), {'root': self.root, 'with_resources': True}))
        code, headers, _ = self.request(capture, self.prefix + 'work/artifact.html')
        self.assertEqual(code, 200)
        self.assertNotIn('sandbox', headers['Content-Security-Policy'])
        self.assertIsNone(self.request(capture, self.prefix + 'trajectory/session.html')[1].get('Content-Security-Policy'))

    def test_resource_base_configuration(self):
        self.assertEqual(resource_base_url('https://assets.example/bucket/'), 'https://assets.example/bucket')
        for value in ['file:///tmp', 'https://user:secret@assets.example', '//assets.example', 'https://assets.example?x=1']:
            with self.assertRaises(ValueError):
                resource_base_url(value)
