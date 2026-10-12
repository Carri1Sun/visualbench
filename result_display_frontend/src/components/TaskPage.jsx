import { ArrowLeft, ArrowUpRight, Braces, Check, ChevronDown, Clock3, Columns2, ExternalLink, FileText, Link2, Maximize, Paperclip, Plus, Repeat2 } from 'lucide-react';
import { asText, categoryLabel, caseKey, formatDuration, getRunCount, inputLabel, safeHref, statusInfo, summarize, taskNumber, trackLabel } from '../lib/data.js';
import { ObservationBadge } from './Observations.jsx';
import { EmptyState, Loading, ModelMark, StatusBadge, TextBlock, Thumbnail } from './Common.jsx';

function Source({ source }) {
  if (!source) return <span className="muted">目录未注明</span>;
  if (typeof source === 'string') {
    const href = safeHref(source);
    return href ? <a href={href} target="_blank" rel="noreferrer" className="source-link">{source}<ArrowUpRight size={13} /></a> : <span className="source-value">{source}</span>;
  }
  const href = safeHref(source.url || source.href);
  return <div>{href && <a className="source-link" href={href} target="_blank" rel="noreferrer">{source.title || source.name || href}<ArrowUpRight size={13} /></a>}<details className="source-details"><summary>查看来源原始记录</summary><pre>{asText(source)}</pre></details></div>;
}

function RunCell({ slot, selected, onResult, onSelect }) {
  const failed = statusInfo(slot.status).group === 'failed';
  return <article className={`run-cell ${selected ? 'selected' : ''}`}>
    <button className="run-cell-media" onClick={() => onResult(slot)} title={`查看 ${slot.model.label || slot.model.id} · Run ${slot.number} 的真实结果`}><Thumbnail slot={slot} task={slot.task} compact /><span className="run-media-open"><Maximize size={14} /></span></button>
    <div className="run-cell-info"><p className="run-phase">思考请求：{slot.run?.thinking_requested || '未知'}</p><div className="run-status-row"><StatusBadge status={slot.status} small /><span className="run-duration" title="索引记录的运行耗时"><Clock3 size={11} />{formatDuration(slot.run?.duration_ms)}</span></div>{slot.run?.phase && statusInfo(slot.status).group === 'active' && <p className="run-phase">阶段：{asText(slot.run.phase)}</p>}{failed && <p className="run-error-summary" title={asText(slot.run?.error)}>{asText(slot.run?.error) || '索引标记此运行失败，未提供错误说明。'}</p>}{!slot.run && <p className="run-not-recorded">尚未写入运行记录</p>}<ObservationBadge runId={slot.run?.id} /><div className="run-cell-actions"><button className="button small ghost" onClick={() => onResult(slot)} title="查看画面、公开方案、Prompt、源码与运行记录">查看详情<ArrowUpRight size={13} /></button><button className={`compare-select-button ${selected ? 'selected' : ''}`} onClick={() => onSelect(slot)} disabled={!slot.run} aria-pressed={selected} aria-label={selected ? '移出对比' : '加入对比'} title={slot.run ? selected ? '移出对比' : '加入对比（最多 4 个）' : '真实运行记录到达后可加入对比'}>{selected ? <Check size={14} /> : <Plus size={14} />}<span>{selected ? '已选' : '对比'}</span></button></div></div>
  </article>;
}

export default function TaskPage({ task, library, live, selectedIds, onHome, onResult, onSelect }) {
  if (!task) return <div className="page-empty">{live.loading ? <Loading /> : <EmptyState title={live.catalog ? '没有找到这道题目' : '任务目录暂时不可用'} description={live.catalog ? '请检查深链接中的任务 ID，或返回作品库。' : '连接恢复后会自动读取此任务。'}><button className="button outline" onClick={onHome} title="返回作品库"><ArrowLeft size={16} />返回作品库</button></EmptyState>}</div>;
  const slots = library.byCase.get(caseKey(task)) || [];
  const repeats = getRunCount(live.catalog, live.index);
  const stats = summarize(slots);
  return <div className="task-page">
    <div className="breadcrumbs"><button onClick={onHome} title="返回作品库"><ArrowLeft size={16} />作品库</button><span>/</span><span>{trackLabel(task.track)}</span><span>/</span><span>{task.case_id || task.id}</span></div>
    <section className="task-intro"><div className="eyebrow"><span className="red-label">{trackLabel(task.track)}</span><span className="eyebrow-divider" /><span>题目 {taskNumber(task)}</span></div><div className="task-intro-heading"><div><h1>{task.title || task.case_id}</h1>{task.description && <p>{asText(task.description)}</p>}</div><div className="task-completion"><span>已有真实产物</span><strong>{stats.succeeded}<small> / {stats.total}</small></strong></div></div><div className="task-specs"><span><Braces size={14} />{trackLabel(task.track)}</span>{task.category && <span>{categoryLabel(task.category)}</span>}<span>{inputLabel(task.input_mode)}</span>{task.width && task.height ? <span><Maximize size={13} />{task.width} × {task.height}</span> : null}{task.duration_seconds != null && <span><Clock3 size={14} />{task.duration_seconds} 秒</span>}<span><Repeat2 size={14} />每模型 {repeats} 次独立运行</span></div></section>
    <section className="task-input-panel" aria-label="任务原始输入"><div className="input-source-row"><div className="source-label"><Link2 size={15} />题目来源</div><Source source={task.source} /></div><div className="input-assets-row"><div className="source-label"><Paperclip size={15} />输入资源</div><div className="input-assets-content">{task.assets?.length ? <div className="asset-links">{task.assets.map((asset, number) => {
      const href = safeHref(asset.url);
      return href ? <a href={href} target="_blank" rel="noreferrer" key={`${asset.url}-${number}`} title="打开题目的原始输入素材"><FileText size={14} />{asset.name || `资源 ${number + 1}`}<ExternalLink size={12} /></a> : <span className="unavailable-asset" key={number}>{asset.name || `资源 ${number + 1}`} · 链接不可用</span>;
    })}</div> : <span className="muted">目录未附加输入文件</span>}<small>输入素材供题目追溯使用。</small></div></div><details className="prompt-details"><summary><span><FileText size={16} />完整 Prompt<span className="subtle-tag">题目原文</span></span><span className="prompt-expand-label">展开查看<ChevronDown size={16} /></span></summary><div className="prompt-details-body">{task.prompt ? <TextBlock text={asText(task.prompt)} filename={`${task.case_id || 'task'}-prompt.txt`} title="提供给模型的完整任务输入" /> : <EmptyState compact title="目录尚未提供 Prompt" description="不补写或推测任务输入，原文到达后将自动显示。" />}</div></details></section>
    <section className="results-matrix-section" aria-labelledby="matrix-heading"><div className="section-heading"><div><h2 id="matrix-heading">同一道题，每一次尝试。</h2><p>{library.models.length} 个模型 × {repeats} 次独立运行 · 按运行次数对齐，不择优展示。</p></div><span className="matrix-select-hint"><Columns2 size={16} />选择 2–4 个结果，横向对比</span></div><div className="matrix-scroll" tabIndex={0} role="region" aria-label="模型与重复运行结果矩阵，可横向滚动"><div className="results-matrix" style={{ '--run-columns': repeats, minWidth: `${Math.max(760, 190 + repeats * 245)}px` }}><div className="matrix-column-head"><div>参与模型</div>{Array.from({ length: repeats }, (_, number) => <div key={number}><span className="run-head-tag">第 {number + 1} 次</span></div>)}</div>{library.models.map((model) => {
      const modelSlots = slots.filter((slot) => slot.model.id === model.id);
      const modelStats = summarize(modelSlots);
      const thinkingSettings = [...new Set(modelSlots.map((slot) => slot.run?.thinking_requested).filter(Boolean))];
      return <div className="matrix-model-row" key={model.id}><div className="matrix-model-label"><ModelMark model={model} /><h3>{model.label || model.id}</h3><p>{model.provider || '模型'}</p><span className="thinking-setting" title="本题各次运行的请求档位">请求档位：{thinkingSettings.join(' / ') || '未知'}</span><span className="model-run-summary">{modelStats.succeeded} / {repeats} 次已产出</span></div>{modelSlots.map((slot) => <RunCell key={slot.id} slot={slot} selected={selectedIds.has(slot.id)} onResult={onResult} onSelect={onSelect} />)}</div>;
    })}</div></div>{library.models.length === 0 && <EmptyState compact title="尚无参与模型" description="目录配置模型后，运行矩阵将自动出现。" />}</section>
  </div>;
}
