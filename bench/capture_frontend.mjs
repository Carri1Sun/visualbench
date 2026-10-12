// Executed by ego-browser nodejs. The Python runner supplies benchConfig.
// Only documented Ego Page/TaskSpace methods and CDP are used here.
const fs = await import('node:fs/promises');
const path = await import('node:path');
const cfg = benchConfig;
await fs.mkdir(cfg.captureDir, {recursive: true});
await fs.mkdir(path.join(cfg.captureDir, 'frames'), {recursive: true});
const statePath = cfg.spacePath;
let state;
try { state = JSON.parse(await fs.readFile(statePath, 'utf8')); } catch (e) {
  if (e.code !== 'ENOENT') throw e;
}
// A stopped existing space is never replaced, reclaimed, or retried automatically.
const task = await taskSpace(state?.spaceId ?? 'VisualBench model evaluation');
state ??= {spaceId: task.spaceId, page: 'p1'};
await fs.writeFile(statePath, JSON.stringify(state, null, 2) + '\n');
const page = task.page(state.page || 'p1');
const consoleEvents = [];
const frames = [];
let recording = false;
let posterAtMs = null;
let desktopInfo = null;
let mobileInfo = null;
let captureStarted = null;
let initScriptId = null;
const started = performance.now();

async function collectEvents() {
  for (const event of await page.events()) {
    if (event.method === 'Page.screencastFrame') {
      const p = event.params;
      const name = `frame-${String(frames.length).padStart(5, '0')}.jpg`;
      await fs.writeFile(path.join(cfg.captureDir, 'frames', name), Buffer.from(p.data, 'base64'));
      frames.push({file: name, timestamp: p.metadata.timestamp, received_ms: performance.now() - captureStarted});
      await page.cdp('Page.screencastFrameAck', {sessionId: p.sessionId});
    } else if (['Runtime.consoleAPICalled', 'Runtime.exceptionThrown', 'Log.entryAdded', 'Network.loadingFailed'].includes(event.method)) {
      consoleEvents.push(event);
    }
  }
}

try {
  await page.cdp('Page.enable');
  await page.cdp('Runtime.enable');
  await page.cdp('Log.enable');
  await page.cdp('Network.enable');
  await page.cdp('Network.setCacheDisabled', {cacheDisabled: true});
  await page.goto('about:blank');
  // The runner reserves this origin solely for capture. Gallery / interactive
  // user previews use a different host and port and are never cleared here.
  const origin = new URL(cfg.url).origin;
  if (origin !== 'http://capture.localhost:4175') throw new Error('Refusing to clear a non-capture origin: ' + origin);
  await page.cdp('Storage.clearDataForOrigin', {origin, storageTypes: 'all'});
  const initScript = await page.cdp('Page.addScriptToEvaluateOnNewDocument', {
    source: 'try { sessionStorage.clear(); } catch (_) {}',
  });
  initScriptId = initScript.identifier;
  await page.cdp('Emulation.setDeviceMetricsOverride', {width: 1280, height: 800, deviceScaleFactor: 1, mobile: false});
  await page.events(); // Discard events belonging to the previous run.
  await page.goto(cfg.url, {waitUntil: 'load', timeout: 45000});
  captureStarted = performance.now();
  await page.cdp('Page.startScreencast', {format: 'jpeg', quality: 90, maxWidth: 1280, maxHeight: 800, everyNthFrame: 1});
  recording = true;
  // Fixed wall-clock observations are intentional experimental conditions.
  while (performance.now() - captureStarted < 8000) {
    await collectEvents();
    if (posterAtMs === null && performance.now() - captureStarted >= 2000) {
      posterAtMs = performance.now() - captureStarted;
      await page.screenshot({path: path.join(cfg.captureDir, 'poster.png'), fullPage: false});
    }
    await page.waitForTimeout(35);
  }
  await page.cdp('Page.stopScreencast');
  recording = false;
  await collectEvents();
  desktopInfo = await page.evaluate(() => ({
    width: innerWidth, height: innerHeight, scroll_width: document.documentElement.scrollWidth,
    scroll_height: document.documentElement.scrollHeight, title: document.title,
    ready_state: document.readyState, canvas_count: document.querySelectorAll('canvas').length,
    svg_count: document.querySelectorAll('svg').length,
    body_children: document.body?.children.length ?? 0,
  }));
  await fs.writeFile(path.join(cfg.captureDir, 'snapshot.txt'), String(await page.snapshot({scope: 'full_page'})));
  if (cfg.mobile) {
    await page.cdp('Emulation.setDeviceMetricsOverride', {width: 390, height: 844, deviceScaleFactor: 1, mobile: false});
    await page.reload({waitUntil: 'load', timeout: 45000});
    await page.waitForTimeout(2000);
    await page.screenshot({path: path.join(cfg.captureDir, 'mobile.png'), fullPage: false});
    mobileInfo = await page.evaluate(() => ({width: innerWidth, height: innerHeight, scroll_width: document.documentElement.scrollWidth}));
    await collectEvents();
  }
  const result = {status: 'captured', space_id: task.spaceId, page: page.label, url: cfg.url,
    desktop: desktopInfo, mobile: mobileInfo, capture_duration_ms: 8000, poster_at_ms: posterAtMs,
    frame_count: frames.length, frames, interaction: 'passive, no input events',
    storage_isolation: 'Dedicated capture.localhost:4175 origin; origin storage cleared before each run; sessionStorage cleared before document scripts; HTTP cache disabled',
    clock: 'wall clock after load; native requestAnimationFrame; no random seed override',
    elapsed_ms: performance.now() - started};
  await fs.writeFile(path.join(cfg.captureDir, 'capture.json'), JSON.stringify(result, null, 2) + '\n');
  console.log(JSON.stringify({status: 'captured', frame_count: frames.length, space_id: task.spaceId}));
} finally {
  await fs.writeFile(path.join(cfg.captureDir, 'console.json'), JSON.stringify(consoleEvents, null, 2) + '\n');
  if (recording) {
    // Cleanup only; an ownership failure still propagates to the parent.
    try { await page.cdp('Page.stopScreencast'); } catch {}
  }
  if (initScriptId) {
    try { await page.cdp('Page.removeScriptToEvaluateOnNewDocument', {identifier: initScriptId}); } catch {}
  }
  try { await page.cdp('Emulation.setDeviceMetricsOverride', {width: 1280, height: 800, deviceScaleFactor: 1, mobile: false}); } catch {}
}
