import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createNavigation, parseRoute } from '../lib/navigation.js';

export default function useRoute(ready) {
  const [route, setRoute] = useState(() => parseRoute(window.location.hash));
  const navigation = useRef(null);
  useEffect(() => {
    const controller = createNavigation(window, setRoute);
    navigation.current = controller;
    return () => { controller.dispose(); navigation.current = null; };
  }, []);
  useLayoutEffect(() => {
    if (!ready) return;
    const frame = requestAnimationFrame(() => navigation.current?.restoreScroll());
    return () => cancelAnimationFrame(frame);
  }, [route, ready]);
  return {
    route,
    navigate: (...args) => navigation.current?.navigate(...args),
    setFilters: (update, options) => navigation.current?.updateFilters(update, options?.push),
    setSort: sort => navigation.current?.setSort(sort),
    openResult: (key, runId) => navigation.current?.openOverlay({ type: 'result', key, runId }),
    openCompare: entries => navigation.current?.openOverlay({ type: 'compare', entries }),
    closeOverlay: () => navigation.current?.closeOverlay(),
    returnToLibrary: () => navigation.current?.returnToLibrary(),
  };
}
