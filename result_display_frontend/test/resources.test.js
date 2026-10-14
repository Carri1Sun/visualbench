import test from 'node:test';
import assert from 'node:assert/strict';
import { createResourceResolver } from '../src/lib/resources.js';

test('resource URLs use the configured origin and prefix, and remain idempotent', () => {
  const r = createResourceResolver('http://127.0.0.1:4180/bucket/');
  for (const path of ['/results/runs/a/video.mp4', '/inputs/video/reference.png']) {
    assert.equal(r.resourceUrl(path), `http://127.0.0.1:4180/bucket${path}`);
    assert.equal(r.resourceUrl(r.resourceUrl(path)), r.resourceUrl(path));
  }
  assert.equal(r.resultUrl('/inputs/video/reference.png'), null);
  assert.equal(r.resourceUrl('https://other.example/results/a.html'), null);
  assert.equal(r.resourceUrl('http://127.0.0.1:4180/bucket-evil/results/a.html'), null);
});

test('reject traversal, malformed escapes, protocol-relative URLs and hidden origin changes', () => {
  const r = createResourceResolver('https://assets.example');
  for (const value of [null, '//evil.example/results/a', '/api/index', '/results/../private', '/results/%2e%2e/private', '/results/%252e%252e/private', '/results/a%5cb', '/results/%00x', '/results/%zz', '/results/a\nb', '/results//evil', 'javascript:alert(1)', 'https://assets.example/results/../private']) {
    assert.equal(r.resourceUrl(value), null, String(value));
  }
});

test('download URL preserves the object path and forces attachment with Unicode filename', () => {
  const r = createResourceResolver('https://assets.example');
  const url = new URL(r.downloadUrl('/results/trace.html?v=2', '运行轨迹.html'));
  assert.equal(url.pathname, '/results/trace.html');
  assert.equal(url.searchParams.get('v'), '2');
  assert.equal(url.searchParams.get('download'), '1');
  assert.equal(url.searchParams.get('filename'), '运行轨迹.html');
  assert.equal(r.downloadUrl(url.href, '运行轨迹.html'), url.href);
  assert.equal(r.downloadUrl('https://evil.example/results/x'), null);
});

test('empty configuration supports explicit same-origin compatibility', () => {
  const r = createResourceResolver('');
  assert.equal(r.resourceUrl('/results/video.mp4'), '/results/video.mp4');
  assert.equal(r.downloadUrl('/inputs/a.png'), '/inputs/a.png?download=1');
});

test('configuration rejects credentials, non-HTTP protocols and query strings', () => {
  for (const base of ['file:///tmp', 'https://user:secret@assets.example', 'https://assets.example?x=1', 'https://assets.example/#x', 'https://assets.example\\evil']) {
    assert.throws(() => createResourceResolver(base));
  }
});
