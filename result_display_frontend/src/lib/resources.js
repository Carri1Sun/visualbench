// Resolve only published resource paths against the configured resource service.
// Keep this independent of React so the same policy can be tested in Node.
export function createResourceResolver(base = '') {
  if (typeof base !== 'string') throw new Error('资源地址必须是字符串');
  base = base.trim().replace(/\/+$/, '');
  if (base) {
    const parsed = new URL(base);
    if (!['http:', 'https:'].includes(parsed.protocol) || parsed.username || parsed.password || parsed.search || parsed.hash || /[\s\\]/.test(base)) {
      throw new Error('资源地址必须是无凭据、无查询参数的 HTTP(S) 地址');
    }
    base = parsed.href.replace(/\/+$/, '');
  }
  function resourceUrl(value, prefix) {
    if (typeof value !== 'string' || /[\u0000-\u0020\u007f\\]/.test(value)) return null;
    let path = value;
    if (/^https?:\/\//.test(path)) {
      if (!base || !path.startsWith(`${base}/`)) return null;
      path = path.slice(base.length);
    }
    const pathname = path.split(/[?#]/, 1)[0];
    let decoded;
    try { decoded = decodeURIComponent(pathname); } catch { return null; }
    if (/%[0-9a-f]{2}/i.test(decoded) || /[\u0000-\u001f\u007f\\]/.test(decoded) || decoded.includes('//') || decoded.split('/').some(part => part === '.' || part === '..')) return null;
    if (!['/results/', '/inputs/'].some(root => pathname.startsWith(root)) || prefix && !pathname.startsWith(prefix)) return null;
    return `${base}${path}`;
  }
  function downloadUrl(value, filename) {
    const resolved = resourceUrl(value);
    if (!resolved) return null;
    const url = new URL(resolved, 'http://local.invalid');
    url.searchParams.set('download', '1');
    if (filename) url.searchParams.set('filename', filename);
    return base ? url.href : `${url.pathname}${url.search}${url.hash}`;
  }
  return { resourceUrl, resultUrl: value => resourceUrl(value, '/results/'), downloadUrl };
}

export const resourceBaseOverride = import.meta.env?.VITE_RESOURCE_BASE_URL;
let resolver = createResourceResolver(resourceBaseOverride ?? '');
export function configureResources(base) { resolver = createResourceResolver(resourceBaseOverride ?? base); }
export const resourceUrl = value => resolver.resourceUrl(value);
export const resultUrl = value => resolver.resultUrl(value);
export const downloadUrl = (value, filename) => resolver.downloadUrl(value, filename);
