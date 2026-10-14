import { useCallback, useEffect, useState } from 'react';
import { resultPath, prettyText } from '../lib/data.js';

export default function useTextFile(path, enabled = true) {
  const safe = resultPath(path);
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState({ path: null, loading: false, text: '', error: null, binary: false });
  const retry = useCallback(() => setAttempt((number) => number + 1), []);

  useEffect(() => {
    if (!safe || !enabled) return;
    const controller = new AbortController();
    let alive = true;
    const timeout = setTimeout(() => controller.abort(), 20000);
    setState({ path: safe, loading: true, text: '', error: null, binary: false });
    fetch(safe, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(`HTTP ${response.status} · 文件暂时不可用`);
        const type = response.headers.get('content-type') || '';
        const binary = /^(video|image|audio)\//.test(type) || /application\/(zip|pdf|octet-stream)/.test(type) && /\.(zip|pdf|gz|mp4|webm)(?:[?#]|$)/i.test(safe);
        return { text: binary ? '' : prettyText(await response.text()), binary };
      })
      .then((result) => { if (alive) setState({ path: safe, loading: false, error: null, ...result }); })
      .catch((error) => {
        if (alive) setState({ path: safe, loading: false, text: '', binary: false, error: error.name === 'AbortError' ? '读取超时，请重试' : error.message });
      })
      .finally(() => clearTimeout(timeout));
    return () => { alive = false; clearTimeout(timeout); controller.abort(); };
  }, [safe, enabled, attempt]);

  if (!safe) return { loading: false, text: '', error: null, missing: true, retry };
  if (state.path !== safe) return { loading: enabled, text: '', error: null, missing: false, retry };
  return { ...state, missing: false, retry };
}
