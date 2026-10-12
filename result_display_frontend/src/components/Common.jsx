import { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { AlertCircle, Check, Clapperboard, Copy, Download, FileQuestion, Loader2, Monitor, RefreshCw, X } from 'lucide-react';
import { asText, downloadText, resultPath, statusInfo, taskNumber } from '../lib/data.js';

export function StatusBadge({ status, small = false }) {
  const info = statusInfo(status);
  return <span className={`status-badge ${info.className} ${small ? 'small' : ''}`}><i className="status-dot" />{info.label}</span>;
}

export function ModelMark({ model, small = false }) {
  const name = model.label || model.id || '?';
  return <span className={`model-mark ${small ? 'small' : ''}`} aria-hidden="true">{name.slice(0, 1).toUpperCase()}</span>;
}

export function Placeholder({ task, status = 'unreported', run, compact = false, broken = false }) {
  const Icon = task?.track === 'video' ? Clapperboard : Monitor;
  const group = statusInfo(status).group;
  let heading = '等待真实结果';
  let caption = '产物就绪后将在这里展示';
  if (group === 'active') { heading = '真实结果生成中'; caption = '运行状态每 10 秒自动更新'; }
  if (group === 'failed') { heading = '本次运行未完成'; caption = '错误与已有文件仍然保留'; }
  if (group === 'succeeded') { heading = run?.video_path ? '真实视频已生成' : '产物已生成'; caption = '尚未提供可用的真实截图'; }
  if (broken) { heading = '截图暂时无法读取'; caption = '可在详情中打开原始文件'; }
  return <div className={`media-placeholder ${compact ? 'compact' : ''} ${group === 'failed' ? 'failed' : ''}`}>
    {!compact && task && <span className="placeholder-number" aria-hidden="true">{taskNumber(task).padStart(2, '0')}</span>}
    <span className="placeholder-orbit"><Icon size={compact ? 22 : 28} strokeWidth={1.4} /></span>
    <span className="placeholder-title">{heading}</span>
    {!compact && <span className="placeholder-caption">{caption}</span>}
  </div>;
}

export function Thumbnail({ slot, task, compact = false }) {
  const path = resultPath(slot?.run?.screenshot_path);
  const [broken, setBroken] = useState(false);
  useEffect(() => setBroken(false), [path]);
  return path && !broken
    ? <img className="real-thumbnail" src={path} alt={`${task.title} · ${slot.model.label} · 第 ${slot.number} 次运行的真实截图`} loading="lazy" onError={() => setBroken(true)} />
    : <Placeholder task={task} compact={compact} status={slot?.status} run={slot?.run} broken={broken} />;
}

export function Loading({ label = '正在读取真实数据…', compact = false }) {
  return <div className={`loading-state ${compact ? 'compact' : ''}`} role="status"><Loader2 size={compact ? 18 : 26} className="spin" /><span>{label}</span></div>;
}

export function EmptyState({ icon: Icon = FileQuestion, title, description, children, compact = false }) {
  return <div className={`empty-state ${compact ? 'compact' : ''}`}>
    <div className="empty-icon"><Icon size={32} strokeWidth={1.4} /></div>
    <h3>{title}</h3>
    {description && <p>{description}</p>}
    {children && <div className="empty-actions">{children}</div>}
  </div>;
}

export function ConnectionBanner({ live }) {
  const errors = Object.entries(live.errors);
  if (!errors.length) return null;
  return <div className="connection-banner" role="status">
    <AlertCircle size={19} />
    <div><strong>数据连接失败{live.catalog || live.index ? ' · 显示最后读取的数据' : ''}</strong><span>{errors.map(([key, error]) => `${({ catalog: '任务目录', index: '结果索引', trajectories: '运行轨迹', audits: '输入校验' })[key] || key}：${error}`).join('；')}。10 秒后自动重试。</span></div>
    <button className="button small outline" onClick={live.refresh} disabled={live.refreshing} title="重新读取任务目录与结果索引"><RefreshCw size={15} className={live.refreshing ? 'spin' : ''} />重试</button>
  </div>;
}

let openDialogs = 0;
let originalOverflow = '';

export function Dialog({ children, onClose, title, className = '' }) {
  const root = useRef(null);
  const id = useId();
  const closeRef = useRef(onClose);
  closeRef.current = onClose;
  useEffect(() => {
    const previous = document.activeElement;
    if (openDialogs++ === 0) {
      originalOverflow = document.body.style.overflow;
      document.body.style.overflow = 'hidden';
    }
    root.current?.focus({ preventScroll: true });
    const keydown = (event) => {
      if (event.key === 'Escape') { event.preventDefault(); closeRef.current(); }
      if (event.key !== 'Tab') return;
      const items = [...(root.current?.querySelectorAll('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea, video[controls], iframe, [tabindex="0"]') || [])].filter((el) => el.getClientRects().length);
      if (!items.length) { event.preventDefault(); return; }
      const first = items[0];
      const last = items.at(-1);
      if (event.shiftKey && (document.activeElement === first || document.activeElement === root.current)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && (document.activeElement === last || document.activeElement === root.current)) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', keydown);
    return () => {
      document.removeEventListener('keydown', keydown);
      if (--openDialogs === 0) document.body.style.overflow = originalOverflow;
      if (previous?.isConnected) previous.focus({ preventScroll: true });
    };
  }, []);
  return createPortal(<div className="dialog-backdrop" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <section ref={root} className={`dialog ${className}`} role="dialog" aria-modal="true" aria-labelledby={id} tabIndex={-1}>
      <span className="sr-only" id={id}>{title}</span>
      {children}
    </section>
  </div>, document.body);
}

export function CloseButton({ onClick }) {
  return <button className="icon-button close-button" onClick={onClick} title="关闭（Esc）" aria-label="关闭弹窗"><X size={21} /></button>;
}

export function CopyButton({ text, label = '复制' }) {
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);
  const timer = useRef(null);
  useEffect(() => () => clearTimeout(timer.current), []);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(asText(text));
      setCopied(true); setFailed(false);
    } catch { setFailed(true); }
    clearTimeout(timer.current);
    timer.current = setTimeout(() => { setCopied(false); setFailed(false); }, 2200);
  };
  return <button className="button small ghost" onClick={copy} title={failed ? '浏览器未允许复制，请手动选择文本' : label}>{copied ? <Check size={14} /> : <Copy size={14} />}{copied ? '已复制' : failed ? '复制不可用' : label}</button>;
}

export function TextBlock({ text, title, filename, actions = true }) {
  return <div className="text-block">
    {(title || actions) && <div className="file-toolbar"><span>{title || filename || '原始内容'}</span>{actions && <div className="file-actions"><CopyButton text={text} />{filename && <button className="button small ghost" onClick={() => downloadText(asText(text), filename)} title={`下载 ${filename}`}><Download size={14} />下载</button>}</div>}</div>}
    <pre tabIndex={0}>{asText(text) || '文件内容为空。'}</pre>
  </div>;
}

export function FileContent({ resource, path, emptyTitle, emptyDescription, title }) {
  const safe = resultPath(path);
  return <div className="file-content">
    {safe && <div className="file-toolbar"><span title={safe}>{title || safe.split('/').pop()}</span><div className="file-actions">{resource.text && <CopyButton text={resource.text} />}<a className="button small ghost" href={safe} download target="_blank" rel="noreferrer" title="下载原始文件"><Download size={14} />下载</a></div></div>}
    {resource.missing ? <EmptyState compact title={emptyTitle || '尚未提供文件'} description={emptyDescription || '结果索引未提供对应路径；有文件后会自动显示。'} />
      : resource.loading ? <Loading compact label="正在读取原始文件…" />
      : resource.error ? <EmptyState compact icon={AlertCircle} title="文件读取失败" description={resource.error}><button className="button outline small" onClick={resource.retry} title="重新读取文件"><RefreshCw size={14} />重试</button></EmptyState>
      : resource.binary ? <EmptyState compact title="此文件不支持文本预览" description="请下载原始文件查看。" />
      : <pre className="file-pre" tabIndex={0}>{resource.text || '文件内容为空。'}</pre>}
  </div>;
}
