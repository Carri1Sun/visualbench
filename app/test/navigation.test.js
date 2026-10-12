import test from 'node:test';
import assert from 'node:assert/strict';
import { createNavigation, parseRoute, routeHash } from '../src/lib/navigation.js';

function setup(hash = '#/') {
  const listeners = new Map();
  const stack = [{ hash, state: null }];
  let cursor = 0;
  const browser = {
    location: { hash }, scrollX: 0, scrollY: 0,
    addEventListener(type, fn) { if (!listeners.has(type)) listeners.set(type, new Set()); listeners.get(type).add(fn); },
    removeEventListener(type, fn) { listeners.get(type)?.delete(fn); },
    requestAnimationFrame: () => 1, cancelAnimationFrame() {},
    scrollTo({ left, top }) { this.scrollX = left; this.scrollY = top; },
  };
  const emit = type => listeners.get(type)?.forEach(fn => fn());
  const traverse = offset => {
    if (!stack[cursor + offset]) return;
    cursor += offset; browser.location.hash = stack[cursor].hash;
    emit('popstate'); emit('hashchange');
  };
  browser.history = {
    scrollRestoration: 'auto',
    get state() { return stack[cursor].state; },
    pushState(state, _, hash) { stack.splice(cursor + 1); stack.push({ hash, state }); cursor++; browser.location.hash = hash; },
    replaceState(state, _, hash) { stack[cursor] = { hash, state }; browser.location.hash = hash; },
    back: () => traverse(-1), forward: () => traverse(1),
  };
  let route;
  const navigation = createNavigation(browser, value => { route = value; });
  return { browser, navigation, stack, get route() { return route; }, get cursor() { return cursor; } };
}

const result = runId => ({ type: 'result', key: 'frontend/test', runId });

test('closed A is discarded when B opens; back closes B and returns to the previous page', () => {
  const s = setup();
  s.navigation.navigate('case', 'frontend/test');
  s.navigation.openOverlay(result('A'));
  s.navigation.closeOverlay();
  s.navigation.openOverlay(result('B'));
  assert.equal(s.stack.length, 3);
  assert.ok(!s.stack.some(entry => entry.hash.includes('result=A')));
  s.browser.history.back();
  assert.equal(s.route.page, 'case'); assert.equal(s.route.overlay, undefined);
  s.browser.history.back();
  assert.equal(s.route.page, 'home');
});

test('browser back/forward toggles the current dialog without duplicating pages', () => {
  const s = setup();
  s.navigation.openOverlay(result('B'));
  s.browser.history.back(); assert.equal(s.route.overlay, undefined);
  s.browser.history.forward(); assert.equal(s.route.overlay.runId, 'B');
  s.navigation.closeOverlay(); assert.equal(s.route.page, 'home');
  assert.equal(s.stack.length, 2);
});

test('switching comparison and result keeps one overlay level', () => {
  const s = setup();
  s.navigation.openOverlay({ type: 'compare' });
  s.navigation.openOverlay(result('B'));
  assert.equal(s.stack.length, 2);
  s.navigation.closeOverlay();
  assert.equal(s.route.overlay, undefined);
  s.browser.history.forward(); assert.equal(s.route.overlay.type, 'result');
});

test('leaving an open dialog does not leave it in the back path', () => {
  const s = setup();
  s.navigation.openOverlay(result('A'));
  s.navigation.navigate('protocol');
  assert.equal(s.stack.length, 2);
  s.browser.history.back(); assert.equal(s.route.page, 'home'); assert.equal(s.route.overlay, undefined);
});

test('track visits push, filter/search/sort edits replace, traversal restores their values', () => {
  const s = setup();
  s.navigation.updateFilters(f => ({ ...f, track: 'frontend' }), true);
  s.navigation.updateFilters(f => ({ ...f, search: '鹈鹕' }));
  s.navigation.updateFilters(f => ({ ...f, model: 'sol' }));
  s.navigation.setSort('number');
  assert.equal(s.stack.length, 2);
  s.navigation.updateFilters(f => ({ ...f, track: 'video', category: 'all' }), true);
  s.browser.history.back();
  assert.deepEqual([s.route.filters.track, s.route.filters.search, s.route.filters.model, s.route.sort], ['frontend', '鹈鹕', 'sol', 'number']);
  s.browser.history.back(); assert.equal(s.route.filters.track, 'all');
  s.browser.history.forward(); assert.equal(s.route.filters.track, 'frontend');
});

test('task breadcrumb restores the originating list and its scroll position', () => {
  const s = setup('#/?track=video&sort=number');
  s.navigation.restoreScroll(); s.browser.scrollY = 1200;
  s.navigation.navigate('case', 'video/test');
  s.navigation.restoreScroll(); assert.equal(s.browser.scrollY, 0);
  s.navigation.returnToLibrary(); s.navigation.restoreScroll();
  assert.equal(s.route.page, 'home'); assert.equal(s.route.filters.track, 'video');
  assert.equal(s.route.sort, 'number'); assert.equal(s.browser.scrollY, 1200);
});

test('direct legacy result link closes safely without going back outside the site', () => {
  const s = setup('#/case/frontend%2Ftest/run/A');
  assert.equal(s.route.overlay.runId, 'A');
  s.navigation.closeOverlay();
  assert.equal(s.stack.length, 1); assert.equal(s.route.page, 'case'); assert.equal(s.route.overlay, undefined);
});

test('refresh preserves the managed dialog parent for safe closing', () => {
  const s = setup(); s.navigation.openOverlay(result('A')); s.navigation.dispose();
  let restored;
  const navigation = createNavigation(s.browser, route => { restored = route; });
  navigation.closeOverlay();
  assert.equal(restored.page, 'home'); assert.equal(restored.overlay, undefined);
  navigation.dispose(); assert.equal(s.browser.history.scrollRestoration, 'auto');
});

test('URLs round trip list context, unicode searches, comparison and result identifiers', () => {
  for (const hash of ['#/?track=frontend&search=机械&compare=1', '#/case/video%2Ftest?result=run%3AA', '#/?result=run%3AB&task=video%2Ftest']) {
    const route = parseRoute(hash);
    assert.deepEqual(parseRoute(routeHash(route)), route);
  }
});

test('repeated current navigation does not add history entries', () => {
  const s = setup(); s.navigation.navigate('home'); s.navigation.navigate('home');
  assert.equal(s.stack.length, 1);
});


test('comparison URLs preserve exact run selection and stable aliases after refresh', () => {
  const s = setup();
  const entries = [{ id: 'frontend/sol/test/run-1', alias: 'A' }, { id: 'video/astra/test/run-2', alias: 'C' }];
  s.navigation.openOverlay({ type: 'compare', entries });
  assert.deepEqual(parseRoute(s.browser.location.hash).overlay.entries, entries);
  s.navigation.dispose();
  let refreshed;
  const navigation = createNavigation(s.browser, route => { refreshed = route; });
  assert.deepEqual(refreshed.overlay.entries, entries);
  navigation.closeOverlay(); assert.equal(refreshed.overlay, undefined);
});
