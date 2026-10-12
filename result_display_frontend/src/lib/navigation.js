import { EMPTY_FILTERS } from './data.js';

const STATE_KEY = 'visualbenchNavigation';
const FILTER_KEYS = Object.keys(EMPTY_FILTERS);
const SORTS = ['completed', 'number', 'recent'];
const decode = value => { try { return decodeURIComponent(value || ''); } catch { return ''; } };

export function parseRoute(hash) {
  const [path, query = ''] = hash.replace(/^#\/?/, '').split('?');
  const parts = path.split('/');
  const params = new URLSearchParams(query);
  const filters = { ...EMPTY_FILTERS };
  FILTER_KEYS.forEach(key => { if (params.has(key)) filters[key] = params.get(key); });
  if (!['all', 'frontend', 'video'].includes(filters.track)) filters.track = 'all';
  const route = { page: 'home', filters, sort: SORTS.includes(params.get('sort')) ? params.get('sort') : 'completed' };
  if (parts[0] === 'protocol') route.page = 'protocol';
  if (parts[0] === 'case' && parts[1]) { route.page = 'case'; route.key = decode(parts[1]); }
  const legacyRun = route.page === 'case' && parts[2] === 'run' ? decode(parts[3]) : null;
  const runId = params.get('result') || legacyRun;
  if (runId && (params.get('task') || route.key)) route.overlay = { type: 'result', key: params.get('task') || route.key, runId };
  else if (params.get('compare') === '1') {
    const entries = params.getAll('selection').filter(value => /^[ABCD]:.+/.test(value)).slice(0, 4).map(value => ({ alias: value[0], id: value.slice(2) }));
    route.overlay = { type: 'compare', entries: entries.filter((entry, index) => entries.findIndex(other => other.id === entry.id || other.alias === entry.alias) === index) };
  }
  return route;
}

export function routeHash(route) {
  const path = route.page === 'case' ? `case/${encodeURIComponent(route.key)}` : route.page === 'protocol' ? 'protocol' : '';
  const params = new URLSearchParams();
  FILTER_KEYS.forEach(key => { if (route.filters[key] !== EMPTY_FILTERS[key]) params.set(key, route.filters[key]); });
  if (route.sort !== 'completed') params.set('sort', route.sort);
  if (route.overlay?.type === 'result') {
    params.set('result', route.overlay.runId);
    if (route.overlay.key !== route.key) params.set('task', route.overlay.key);
  }
  if (route.overlay?.type === 'compare') {
    params.set('compare', '1');
    (route.overlay.entries || []).forEach(entry => params.append('selection', `${entry.alias}:${entry.id}`));
  }
  return `#/${path}${params.size ? `?${params}` : ''}`;
}

const baseRoute = route => { const { overlay, ...base } = route; return base; };

// A page has one optional overlay. Opening replaces any existing overlay;
// closing traverses to its parent instead of pushing another page entry.
export function createNavigation(browser, onChange) {
  let current = parseRoute(browser.location.hash);
  let pendingScroll = null;
  let closing = false;
  let nextId = 0;
  let scrollFrame = null;
  const positions = new Map();
  const id = () => `${Date.now()}-${++nextId}-${Math.random().toString(36).slice(2)}`;
  const metadata = () => {
    const value = browser.history.state?.[STATE_KEY];
    return value?.hash === browser.location.hash ? value : null;
  };
  const replaceMetadata = value => browser.history.replaceState({ ...browser.history.state, [STATE_KEY]: value }, '', value.hash);
  const position = () => [browser.scrollX || 0, browser.scrollY || 0];
  const savePosition = () => {
    const meta = metadata();
    if (!meta) return;
    const scroll = position();
    positions.set(meta.id, scroll);
    replaceMetadata({ ...meta, scroll });
  };
  const publish = (route, scroll) => {
    current = route;
    closing = false;
    pendingScroll = scroll;
    onChange(route);
  };
  const write = (route, { replace = false, scroll = position(), overlayParent = null, pageParent = null } = {}) => {
    if (closing) return;
    const hash = routeHash(route);
    if (hash === routeHash(current)) return;
    savePosition();
    const meta = { id: id(), hash, scroll, overlayParent, pageParent };
    browser.history[replace ? 'replaceState' : 'pushState']({ ...browser.history.state, [STATE_KEY]: meta }, '', hash);
    positions.set(meta.id, scroll);
    publish(route, scroll);
  };
  const adopt = () => {
    const route = parseRoute(browser.location.hash);
    const meta = metadata() || { id: id(), hash: browser.location.hash, scroll: [0, 0] };
    replaceMetadata(meta);
    publish(route, positions.get(meta.id) || meta.scroll || [0, 0]);
  };
  const changed = () => {
    // Same-document traversal emits both popstate and hashchange.
    if (browser.location.hash === routeHash(current) && !closing) return;
    adopt();
  };
  const scrolled = () => {
    if (scrollFrame !== null) return;
    const entryId = metadata()?.id;
    scrollFrame = browser.requestAnimationFrame(() => {
      scrollFrame = null;
      if (metadata()?.id === entryId && !pendingScroll) savePosition();
    });
  };
  const previousRestoration = browser.history.scrollRestoration;
  browser.history.scrollRestoration = 'manual';
  adopt();
  browser.addEventListener('popstate', changed);
  browser.addEventListener('hashchange', changed);
  browser.addEventListener('scroll', scrolled, { passive: true });

  return {
    navigate(page, key, filters = current.filters) {
      const parent = metadata();
      const route = { page, ...(page === 'case' ? { key } : {}), filters, sort: current.sort };
      write(route, { replace: Boolean(current.overlay), scroll: [0, 0], pageParent: current.page === 'home' && page !== 'home' ? { id: parent?.id, hash: routeHash(baseRoute(current)) } : null });
    },
    updateFilters(update, push = false) {
      const filters = typeof update === 'function' ? update(current.filters) : update;
      const route = { page: 'home', filters, sort: current.sort };
      const samePage = current.page === 'home';
      write(route, { replace: samePage ? !push || Boolean(current.overlay) : Boolean(current.overlay), scroll: push || !samePage ? [0, 0] : position() });
    },
    setSort(sort) { write({ ...current, sort }, { replace: true }); },
    openOverlay(overlay) {
      const meta = metadata();
      write({ ...baseRoute(current), overlay }, { replace: Boolean(current.overlay), overlayParent: current.overlay ? meta?.overlayParent : meta?.id, pageParent: meta?.pageParent });
    },
    closeOverlay() {
      if (!current.overlay || closing) return;
      if (metadata()?.overlayParent) { closing = true; browser.history.back(); }
      else write(baseRoute(current), { replace: true, pageParent: metadata()?.pageParent });
    },
    returnToLibrary() {
      const parent = metadata()?.pageParent;
      const route = { page: 'home', filters: current.filters, sort: current.sort };
      if (!current.overlay && parent?.id && parent.hash === routeHash(route)) { closing = true; browser.history.back(); }
      else write(route, { replace: true, scroll: [0, 0] });
    },
    restoreScroll() {
      if (!pendingScroll) return;
      const scroll = pendingScroll;
      pendingScroll = null;
      browser.scrollTo({ left: scroll[0], top: scroll[1], behavior: 'instant' });
    },
    dispose() {
      savePosition();
      browser.removeEventListener('popstate', changed);
      browser.removeEventListener('hashchange', changed);
      browser.removeEventListener('scroll', scrolled);
      if (scrollFrame !== null) browser.cancelAnimationFrame(scrollFrame);
      browser.history.scrollRestoration = previousRestoration;
    },
  };
}
