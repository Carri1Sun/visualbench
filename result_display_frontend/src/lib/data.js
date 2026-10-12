export const STATUS = {
  unreported: { label: '等待真实结果', group: 'waiting', className: 'waiting' },
  queued: { label: '排队中', group: 'waiting', className: 'waiting' },
  running: { label: '运行中', group: 'active', className: 'active' },
  generating: { label: '生成中', group: 'active', className: 'active' },
  rendering: { label: '渲染中', group: 'active', className: 'active' },
  awaiting_render: { label: '待采集', group: 'active', className: 'active' },
  interrupted: { label: '中断待恢复', group: 'waiting', className: 'waiting' },
  succeeded: { label: '已产出', group: 'succeeded', className: 'success' },
  generation_failed: { label: '生成失败', group: 'failed', className: 'failed' },
  render_failed: { label: '渲染失败', group: 'failed', className: 'failed' },
};

export const EMPTY_FILTERS = {
  track: 'all', category: 'all', input: 'all', model: 'all', run: 'all', status: 'all', search: '',
};

export function statusInfo(status) {
  return STATUS[status] || { label: status || '状态未知', group: 'waiting', className: 'waiting' };
}

export function caseKey(task) {
  return task.id || `${task.track}/${task.case_id}`;
}

export function getRunCount(catalog, index) {
  const value = Number(catalog?.protocol?.repetitions ?? catalog?.protocol?.runs_per_model ?? index?.protocol?.repetitions ?? index?.protocol?.runs_per_model ?? 3);
  return Number.isInteger(value) && value > 0 ? value : 3;
}

export function buildLibrary(catalog, index) {
  if (!catalog) return { tasks: [], models: [], slots: [], byCase: new Map(), unmatchedRuns: [] };
  const tasks = catalog.cases || [];
  const models = catalog.models || [];
  const repeats = getRunCount(catalog, index);
  const taskByKey = new Map(tasks.map((task) => [caseKey(task), task]));
  const actual = new Map();
  const unmatchedRuns = [];
  for (const run of index?.runs || []) {
    let key = run.case_key;
    if (!taskByKey.has(key)) {
      const matches = tasks.filter((task) =>
        (task.case_id === run.case_id || caseKey(task) === run.case_id) && (!run.track || task.track === run.track),
      );
      key = matches.length === 1 ? caseKey(matches[0]) : null;
    }
    if (!key || !models.some((model) => model.id === run.model_id) || !Number.isInteger(Number(run.run_number)) || Number(run.run_number) < 1 || Number(run.run_number) > repeats) {
      unmatchedRuns.push(run);
      continue;
    }
    const identity = `${key}::${run.model_id}::${Number(run.run_number)}`;
    const previous = actual.get(identity);
    if (!previous || (run.finished_at || run.started_at || '') >= (previous.finished_at || previous.started_at || '')) {
      if (previous) unmatchedRuns.push(previous);
      actual.set(identity, run);
    } else {
      unmatchedRuns.push(run);
    }
  }
  const slots = [];
  const byCase = new Map();
  tasks.forEach((task) => {
    const taskSlots = [];
    models.forEach((model) => {
      for (let number = 1; number <= repeats; number++) {
        const identity = `${caseKey(task)}::${model.id}::${number}`;
        const run = actual.get(identity) || null;
        const slot = {
          id: run?.id || `planned:${identity}`, identity,
          task, model, number, run,
          status: run?.status || 'unreported',
        };
        slots.push(slot);
        taskSlots.push(slot);
      }
    });
    byCase.set(caseKey(task), taskSlots);
  });
  return { tasks, models, slots, byCase, unmatchedRuns };
}

export function summarize(slots) {
  const summary = { total: slots.length, succeeded: 0, active: 0, failed: 0, waiting: 0 };
  slots.forEach((slot) => { summary[statusInfo(slot.status).group]++; });
  summary.ended = summary.succeeded + summary.failed;
  summary.percent = summary.total ? Math.round(summary.ended / summary.total * 100) : 0;
  return summary;
}

export function matchesSlot(slot, filters, taskMatchesSearch = false) {
  if (filters.model !== 'all' && slot.model.id !== filters.model) return false;
  if (filters.run !== 'all' && slot.number !== Number(filters.run)) return false;
  if (filters.status !== 'all' && filters.status !== slot.status && filters.status !== statusInfo(slot.status).group) return false;
  const query = filters.search.trim().toLocaleLowerCase();
  if (query && !taskMatchesSearch && ![slot.model.id, slot.model.label, slot.model.provider, slot.model.model].join(' ').toLocaleLowerCase().includes(query)) return false;
  return true;
}

export function filterLibrary(library, filters, sort = 'number') {
  const query = filters.search.trim().toLocaleLowerCase();
  const results = [];
  for (const task of library.tasks) {
    if (filters.track !== 'all' && task.track !== filters.track) continue;
    if (filters.category !== 'all' && task.category !== filters.category) continue;
    if (filters.input !== 'all' && task.input_mode !== filters.input) continue;
    const taskSearch = !query || [task.title, task.id, task.case_id].join(' ').toLocaleLowerCase().includes(query);
    const all = library.byCase.get(caseKey(task)) || [];
    const matched = all.filter((slot) => matchesSlot(slot, filters, taskSearch));
    const noSlotFilter = filters.model === 'all' && filters.run === 'all' && filters.status === 'all';
    if (matched.length || (!all.length && taskSearch && noSlotFilter)) results.push({ task, slots: all, matched });
  }
  if (sort === 'recent') results.sort((a, b) => lastUpdate(b.slots) - lastUpdate(a.slots));
  if (sort === 'completed') results.sort((a, b) => summarize(b.slots).succeeded - summarize(a.slots).succeeded);
  return results;
}

function lastUpdate(slots) {
  return Math.max(0, ...slots.map((slot) => Date.parse(slot.run?.finished_at || slot.run?.started_at || '') || 0));
}

export function trackLabel(track) {
  return track === 'frontend' ? '前端交互' : track === 'video' ? '视频创作' : track || '未分类';
}

export function inputLabel(mode) {
  return ({ text: '文本输入', image: '图像输入', 'text-only': '纯文本', text_only: '纯文本创作', prompt_only: '仅提示词', text_plus_fixed_fixture: '提示词与固定资料', assets: '附带参考素材', local_assets: '本地参考素材', provided_assets: '指定参考素材', image_to_code: '图像输入', 'text-to-image': '文本输入' })[mode] || mode || '未注明';
}

export function categoryLabel(category) {
  return ({ visual: '视觉创作', simulation: '动态模拟', logic: '逻辑可视化', interactive: '交互体验', product: '产品页面', motion: '动态影像' })[category] || category || '未分类';
}

export function taskNumber(task) {
  return (task.case_id || task.id || '').split('/').pop().match(/^\d+/)?.[0] || '—';
}

export function formatDuration(ms) {
  if (ms === null || ms === undefined || !Number.isFinite(Number(ms))) return '—';
  const seconds = Number(ms) / 1000;
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)} 秒`;
  return `${Math.floor(seconds / 60)} 分 ${Math.round(seconds % 60)} 秒`;
}

export function formatTime(seconds) {
  if (!Number.isFinite(seconds)) return '00:00';
  const safe = Math.max(0, Math.floor(seconds));
  return `${String(Math.floor(safe / 60)).padStart(2, '0')}:${String(safe % 60).padStart(2, '0')}`;
}

export function formatDate(value) {
  if (!value) return '尚未记录';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString('zh-CN', { hour12: false, timeZone: 'Asia/Shanghai' });
}

export function asText(value) {
  return typeof value === 'string' ? value : value === undefined || value === null ? '' : JSON.stringify(value, null, 2);
}

export function prettyText(text) {
  try { return JSON.stringify(JSON.parse(text), null, 2); } catch { return text; }
}

// Only index-provided result paths are fetched; source text is never evaluated.
export function resultPath(path) {
  return typeof path === 'string' && /^\/results\//.test(path) && !path.includes('..') && !/[\r\n\\]/.test(path) ? path : null;
}

export function artifactUrl(path) {
  // Same-origin relative path: vite dev proxy or the production reverse proxy
  // forwards /api, /results and /inputs to result_background.
  return resultPath(path);
}

export function sourcePath(run) {
  if (resultPath(run?.code_path)) return resultPath(run.code_path);
  const artifact = resultPath(run?.artifact_path);
  if (artifact && (/\.html?(?:[?#]|$)/i.test(artifact) || artifact.endsWith('/'))) {
    return artifact.endsWith('/') ? `${artifact}index.html` : artifact;
  }
  return null;
}

export function safeHref(value) {
  if (typeof value !== 'string' || !value.trim() || /[\r\n\\]/.test(value)) return null;
  if (value.startsWith('/') && !value.startsWith('//')) return value;
  try { const url = new URL(value); return ['http:', 'https:'].includes(url.protocol) ? value : null; } catch { return null; }
}

export function downloadText(text, name, type = 'text/plain;charset=utf-8') {
  const url = URL.createObjectURL(new Blob([text], { type }));
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
