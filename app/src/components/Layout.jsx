import { useEffect, useRef } from 'react';
import { ArrowUpRight, Clapperboard, Columns2, FileText, LayoutGrid, Monitor, RefreshCw, Search, X } from 'lucide-react';
import { formatDate } from '../lib/data.js';

export default function Layout({ children, live, route, filters, onHome, onTrack, onProtocol, onCompare, onSearch, selectionCount }) {
  const search = useRef(null);
  useEffect(() => {
    const handler = (event) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault(); search.current?.focus();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);
  const navItems = [
    { id: 'all', label: '作品库', icon: LayoutGrid, active: route.page === 'home' && filters.track === 'all', action: () => onTrack('all') },
    { id: 'frontend', label: '前端', icon: Monitor, active: route.page === 'home' && filters.track === 'frontend', action: () => onTrack('frontend') },
    { id: 'video', label: '视频', icon: Clapperboard, active: route.page === 'home' && filters.track === 'video', action: () => onTrack('video') },
    { id: 'compare', label: '对比', icon: Columns2, action: onCompare, badge: selectionCount },
    { id: 'protocol', label: '实验概况', icon: FileText, active: route.page === 'protocol', action: onProtocol },
  ];
  return <>
    <a href="#main-content" className="skip-link">跳到主要内容</a>
    <header className="topbar">
      <button className="brand" onClick={onHome} title="VisualBench 首页" aria-label="VisualBench 首页"><span className="brand-play"><i /></span><span>Visual<span className="brand-second">Bench</span></span></button>
      <span className="brand-description">视觉实验档案</span>
      <div className="global-search"><Search size={18} strokeWidth={1.8} /><input ref={search} value={filters.search} onChange={(event) => onSearch(event.target.value)} placeholder="搜索题目、任务 ID 或模型" aria-label="搜索题目、任务 ID 或模型" onKeyDown={(event) => { if (event.key === 'Escape') { onSearch(''); search.current.blur(); } }} />{filters.search ? <button className="search-clear" onClick={() => onSearch('')} title="清除搜索" aria-label="清除搜索"><X size={15} /></button> : <kbd>⌘ K</kbd>}</div>
      <div className="header-right"><button className="round-button" onClick={onProtocol} title="查看本轮实验概况"><span className="round-dot" />第 01 轮<ArrowUpRight size={13} /></button><span className={`live-connection ${live.connected ? 'online' : live.loading ? 'connecting' : 'offline'}`} title={`每 10 秒自动读取 · 最后成功连接：${formatDate(live.lastSync)}`}><i />{live.loading ? '连接中' : live.connected ? '实时连接' : '连接失败'}</span><button className="icon-button refresh-button" onClick={live.refresh} disabled={live.refreshing} title="立即同步数据" aria-label="立即同步数据"><RefreshCw size={17} className={live.refreshing ? 'spin' : ''} /></button></div>
    </header>
    <aside className="sidebar" aria-label="主导航"><nav>{navItems.map(({ id, label, icon: Icon, active, action, badge }, position) => <div className={position === 3 ? 'nav-separated' : ''} key={id}><button className={`nav-item ${active ? 'active' : ''}`} onClick={action} title={id === 'compare' ? `结果对比，已选择 ${selectionCount} 个` : label} aria-current={active ? 'page' : undefined}><span className="nav-icon"><Icon size={21} strokeWidth={1.7} />{badge > 0 && <span className="nav-count">{badge}</span>}</span><span>{label}</span></button></div>)}</nav><div className="rail-foot"><span className={`rail-live ${live.connected ? 'online' : ''}`} /><span>OPEN<br />ARCHIVE</span></div></aside>
    <main id="main-content" className="main-content" tabIndex={-1}>{children}<footer className="site-footer"><span className="footer-brand"><span className="tiny-play" />VisualBench</span><button onClick={onProtocol} title="查看数据来源与实验概况">关于这场实验<ArrowUpRight size={13} /></button></footer></main>
  </>;
}
