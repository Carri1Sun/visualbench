import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

async function fetchJSON(path, signal) {
  const response = await fetch(path, { signal, cache: 'no-store', headers: { Accept: 'application/json' } });
  if (!response.ok) throw new Error(`HTTP ${response.status} · ${response.status >= 500 ? '数据服务暂时不可用' : '无法读取文件'}`);
  const value = await response.json();
  if (!value || typeof value !== 'object') throw new Error('数据格式无效');
  if (path.includes('catalog') && (!Array.isArray(value.cases) || !Array.isArray(value.models))) throw new Error('catalog 缺少 cases 或 models 数组');
  if (path.includes('index') && !Array.isArray(value.runs)) throw new Error('结果索引缺少 runs 数组');
  return value;
}

export default function useLiveData() {
  const [state, setState] = useState({ catalog: null, index: null, trajectories: null, audits: null, loading: true, refreshing: false, errors: {}, lastSync: null });
  const alive = useRef(false);
  const inFlight = useRef(false);
  const controller = useRef(null);

  const refresh = useCallback(async () => {
    if (!alive.current || inFlight.current) return;
    inFlight.current = true;
    const abort = new AbortController();
    controller.current = abort;
    const timeout = setTimeout(() => abort.abort(), 15000);
    setState((previous) => ({ ...previous, refreshing: true }));
    const responses = await Promise.allSettled([
      fetchJSON('/data/catalog.json', abort.signal),
      fetchJSON('/results/index.json', abort.signal),
      fetchJSON('/data/trajectories.json', abort.signal),
      fetchJSON('/data/audits.json', abort.signal),
    ]);
    clearTimeout(timeout);
    if (alive.current && controller.current === abort) {
      setState((previous) => {
        const errors = {};
        responses.forEach((result, number) => {
          if (result.status === 'rejected') errors[['catalog', 'index', 'trajectories', 'audits'][number]] = result.reason?.name === 'AbortError' ? '请求超时，请检查数据服务' : result.reason?.message || '网络连接失败';
        });
        return {
          catalog: responses[0].status === 'fulfilled' ? responses[0].value : previous.catalog,
          index: responses[1].status === 'fulfilled' ? responses[1].value : previous.index,
          trajectories: responses[2].status === 'fulfilled' ? responses[2].value : previous.trajectories,
          audits: responses[3].status === 'fulfilled' ? responses[3].value : previous.audits,
          errors, loading: false, refreshing: false,
          lastSync: responses.every((result) => result.status === 'fulfilled') ? new Date().toISOString() : previous.lastSync,
        };
      });
      inFlight.current = false;
    }
  }, []);

  useEffect(() => {
    alive.current = true;
    refresh();
    const timer = setInterval(refresh, 10000);
    return () => {
      alive.current = false;
      clearInterval(timer);
      controller.current?.abort();
      controller.current = null;
      inFlight.current = false;
    };
  }, [refresh]);

  const index = useMemo(() => state.index ? { ...state.index, runs: state.index.runs.map((run) => ({ ...run, ...(state.trajectories?.runs?.[run.id] || {}), audit: state.audits?.runs?.[run.id] || null })) } : null, [state.index, state.trajectories, state.audits]);
  return { ...state, index, refresh, connected: !state.loading && Object.keys(state.errors).length === 0 };
}
