import { Component, useEffect, useMemo, useRef, useState } from 'react';
import { AlertCircle, ArrowLeft, RefreshCw } from 'lucide-react';
import { buildLibrary, caseKey } from './lib/data.js';
import useLiveData from './hooks/useLiveData.js';
import useRoute from './hooks/useRoute.js';
import Layout from './components/Layout.jsx';
import { ObservationProvider } from './components/Observations.jsx';
import Gallery from './components/Gallery.jsx';
import TaskPage from './components/TaskPage.jsx';
import ProtocolPage from './components/ProtocolPage.jsx';
import ResultDialog from './components/ResultDialog.jsx';
import ComparisonDialog, { ComparisonBasket } from './components/Comparison.jsx';
import { CloseButton, ConnectionBanner, Dialog, EmptyState, Loading } from './components/Common.jsx';

class ErrorBoundary extends Component {
  state = { error: null };
  static getDerivedStateFromError(error) { return { error }; }
  render() {
    if (this.state.error) return <div className="fatal-error"><span className="brand-play"><i /></span><h1>页面暂时无法显示</h1><p>没有生成替代结果。请刷新后重试。</p><pre>{this.state.error.message}</pre><button className="button primary" onClick={() => window.location.reload()} title="重新加载页面"><RefreshCw size={16} />重新加载</button></div>;
    return this.props.children;
  }
}

function VisualBench() {
  const live = useLiveData();
  const { route, navigate, setFilters, setSort, openResult: showResult, openCompare: showCompare, closeOverlay, returnToLibrary } = useRoute(Boolean(live.catalog));
  const { filters, sort, overlay } = route;
  const [selections, setSelections] = useState([]);
  const [toast, setToast] = useState('');
  const toastTimer = useRef(null);
  const library = useMemo(() => buildLibrary(live.catalog, live.index), [live.catalog, live.index]);
  const slotsById = useMemo(() => new Map(library.slots.map((slot) => [slot.id, slot])), [library]);
  const selectedEntries = useMemo(() => selections.map((item) => ({ ...item, slot: slotsById.get(item.id) })).filter((item) => item.slot).sort((a, b) => a.alias.localeCompare(b.alias)), [selections, slotsById]);
  const comparisonEntries = useMemo(() => (overlay?.type === 'compare' ? (overlay.entries || []) : []).map((item) => ({ ...item, slot: slotsById.get(item.id) })).filter((item) => item.slot), [overlay, slotsById]);
  const selectedIds = useMemo(() => new Set(selectedEntries.map((entry) => entry.id)), [selectedEntries]);
  const task = library.tasks.find((item) => caseKey(item) === route.key);
  const result = overlay?.type === 'result' ? library.slots.find((slot) => (slot.id === overlay.runId || `planned:${slot.identity}` === overlay.runId) && caseKey(slot.task) === overlay.key) : null;

  useEffect(() => () => clearTimeout(toastTimer.current), []);
  useEffect(() => {
    document.title = route.page === 'protocol' ? '实验概况 · VisualBench' : task ? `${task.title} · VisualBench` : 'VisualBench · 模型的创作，眼见为实。';
  }, [route.page, route.key, task?.title]);
  useEffect(() => {
    if (live.catalog && live.index) setSelections((previous) => previous.filter((entry) => slotsById.has(entry.id)));
  }, [slotsById, live.catalog, live.index]);

  const notify = (message) => {
    setToast(message);
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(''), 3500);
  };
  const select = (slot) => {
    if (!slot.run) { notify('真实运行记录到达后，才能加入对比。'); return; }
    if (selectedIds.has(slot.id)) { setSelections((previous) => previous.filter((entry) => entry.id !== slot.id)); return; }
    if (selections.length >= 4) { notify('最多同时对比 4 个结果，请先移出一个。'); return; }
    const alias = ['A', 'B', 'C', 'D'].find((letter) => !selections.some((entry) => entry.alias === letter));
    setSelections((previous) => [...previous, { id: slot.id, alias }]);
  };
  const home = () => navigate('home');
  const openTask = (item) => navigate('case', caseKey(item));
  const openResult = (slot) => showResult(caseKey(slot.task), slot.id);
  const track = (value) => setFilters((previous) => ({ ...previous, track: value, category: 'all' }), { push: true });
  const search = (value) => setFilters((previous) => ({ ...previous, search: value }));
  const protocol = () => navigate('protocol');
  const openCompare = () => showCompare(selectedEntries.map(({ id, alias }) => ({ id, alias })));

  return <ObservationProvider roundId={live.catalog?.protocol?.round_id || 'unknown'}><Layout live={live} route={route} filters={filters} onHome={home} onTrack={track} onSearch={search} onProtocol={protocol} onCompare={openCompare} selectionCount={selectedEntries.length}>
    <ConnectionBanner live={live} />
    {live.catalog && !live.index && !live.loading && <div className="data-notice"><AlertCircle size={16} />任务目录已读取，运行记录暂不可用。计划运行位正在等待实际结果。</div>}
    {library.unmatchedRuns.length > 0 && <div className="data-notice"><AlertCircle size={16} /><span>有 {library.unmatchedRuns.length} 条实际索引记录未匹配到当前计划矩阵。</span><button onClick={protocol} title="查看未匹配的原始运行记录">查看原始记录</button></div>}
    {route.page === 'home' && <Gallery library={library} live={live} filters={filters} setFilters={setFilters} sort={sort} setSort={setSort} onTask={openTask} onResult={openResult} />}
    {route.page === 'case' && <TaskPage task={task} library={library} live={live} selectedIds={selectedIds} onHome={returnToLibrary} onResult={openResult} onSelect={select} />}
    {route.page === 'protocol' && <ProtocolPage live={live} library={library} onHome={returnToLibrary} />}
    <ComparisonBasket entries={selectedEntries} onRemove={(id) => setSelections((previous) => previous.filter((entry) => entry.id !== id))} onClear={() => setSelections([])} onOpen={openCompare} />
    {overlay?.type === 'result' && (result ? <ResultDialog key={result.id} slot={result} selected={selectedIds.has(result.id)} onSelect={select} onClose={closeOverlay} /> : <Dialog title="读取运行记录" onClose={closeOverlay} className="missing-run-dialog"><CloseButton onClick={closeOverlay} />{live.loading ? <Loading label="正在读取此运行的真实记录…" /> : <EmptyState icon={AlertCircle} title="暂时无法找到此运行" description={live.errors.index ? '结果索引连接失败，请重试。' : '该运行 ID 不在当前任务的结果索引中。'}><button className="button outline" onClick={closeOverlay} title="关闭并返回原页面"><ArrowLeft size={15} />返回原页面</button><button className="button primary" onClick={live.refresh} disabled={live.refreshing} title="重新读取真实结果"><RefreshCw size={15} />重试</button></EmptyState>}</Dialog>)}
    {overlay?.type === 'compare' && <ComparisonDialog entries={comparisonEntries} onClose={closeOverlay} onResult={openResult} />}
    {toast && <div className="toast" role="status"><AlertCircle size={16} />{toast}</div>}
  </Layout></ObservationProvider>;
}

export default function App() {
  return <ErrorBoundary><VisualBench /></ErrorBoundary>;
}
