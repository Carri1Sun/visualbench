import { ArrowUpRight, Check, CheckCircle2, Circle, Clock3, Layers3, Radio, Repeat2, Sparkles, TriangleAlert } from 'lucide-react';
import { getRunCount, statusInfo, summarize } from '../lib/data.js';
import { ModelMark } from './Common.jsx';

/* One tick per planned run, in task order: every attempt stays visible. */
function RunTicks({ slots }) {
  const label = slots.map((slot) => statusInfo(slot.status).label).join('、');
  return <div className="run-ticks" role="img" aria-label={`本模型各次运行状态：${label}`}>
    {slots.map((slot) => <span key={slot.id} className={statusInfo(slot.status).className} style={{ gridRow: slot.number }} title={`第 ${slot.number} 次 · ${statusInfo(slot.status).label}`} />)}
  </div>;
}

export function StatusLegend() {
  return <div className="status-legend"><span><i className="success" />已产出</span><span><i className="active" />进行中</span><span><i className="failed" />失败</span><span><i className="waiting" />等待</span></div>;
}

export default function Dashboard({ library, live }) {
  const stats = summarize(library.slots);
  const known = Boolean(live.catalog);
  const knownRuns = Boolean(live.index);
  const repeats = getRunCount(live.catalog, live.index);
  const thinkingPolicy = live.index?.protocol?.thinking_policy || live.catalog?.protocol?.thinking_policy;
  const facts = [
    { value: known ? library.tasks.length : '—', label: '开放题目', icon: Layers3 },
    { value: known ? library.models.length : '—', label: '参与模型', icon: Sparkles },
    { value: known ? repeats : '—', label: '次独立运行 / 模型', icon: Repeat2 },
    { value: known ? library.slots.length.toLocaleString() : '—', label: '次计划运行', icon: Radio },
  ];
  return <>
    <section className="dashboard-hero">
      <div className="hero-copy"><div className="eyebrow"><span className="red-label">ROUND 01</span><span className="eyebrow-divider" /><span>本轮实验</span><span className="hero-live-tag">持续记录中</span></div><h1>实验概况<span className="red-period">。</span></h1><p className="hero-description">模型的创作，眼见为实。<br />不打分，不排榜。让每一次真实输出，自己说话。<br /><span>相同题目，独立运行。从公开方案到最终产物，完整保留。</span></p><div className="hero-facts">{facts.map(({ value, label, icon: Icon }) => <div className="hero-fact" key={label}><div className="fact-number">{value}<Icon size={17} strokeWidth={1.5} /></div><span>{label}</span></div>)}</div></div>
      <div className="round-progress"><div className="progress-heading"><span>本轮运行进度</span><span className="subtle-tag"><Clock3 size={12} />实时归档</span></div><div className="progress-overview"><div className="progress-ring"><svg viewBox="0 0 120 120" aria-hidden="true"><circle cx="60" cy="60" r="51" className="ring-track" /><circle cx="60" cy="60" r="51" className="ring-value" strokeDasharray={`${2 * Math.PI * 51}`} strokeDashoffset={`${2 * Math.PI * 51 * (1 - stats.percent / 100)}`} /></svg><strong>{known && knownRuns ? stats.percent : '—'}{known && knownRuns && <small>%</small>}</strong></div><div className="progress-summary"><span>已结束 / 计划</span><p><strong>{known && knownRuns ? stats.ended : '—'}</strong><span> / {known ? stats.total : '—'}</span></p><small>按已结束运行统计</small></div></div><div className="progress-stat-grid">{[{ key: 'succeeded', label: '已产出', icon: CheckCircle2, color: 'success' }, { key: 'active', label: '进行中', icon: Radio, color: 'active' }, { key: 'failed', label: '失败', icon: TriangleAlert, color: 'failed' }, { key: 'waiting', label: '等待', icon: Circle, color: 'waiting' }].map(({ key, label, icon: Icon, color }) => <div key={key}><span><Icon size={13} className={`text-${color}`} />{label}</span><strong>{known && knownRuns ? stats[key] : '—'}</strong></div>)}</div><button className="protocol-link" onClick={() => document.getElementById('experiment-details')?.scrollIntoView({ behavior: 'smooth' })} title="了解运行协议与公开范围">查看实验说明<ArrowUpRight size={14} /></button></div>
    </section>
    <section className="model-progress-section" aria-labelledby="model-progress-heading"><div className="section-heading"><div><h2 id="model-progress-heading">模型运行概况<span className="section-kicker">每次运行，完整归档。</span></h2></div><StatusLegend /></div>
      {library.models.length ? <div className="model-progress-grid">{library.models.map((model) => {
        const modelStats = summarize(library.slots.filter((slot) => slot.model.id === model.id));
        return <article className="model-progress-card" key={model.id}><div className="model-card-heading"><ModelMark model={model} /><div><h3 title={model.label || model.id}>{model.label || model.id}</h3><p title={model.model || model.provider}>{model.provider || model.model || '独立运行'}</p></div></div><div className="model-progress-number"><span>已结束 <strong>{knownRuns ? modelStats.ended : '—'}</strong><small> / {modelStats.total}</small></span><span>{knownRuns ? modelStats.percent : '—'}{knownRuns && '%'}</span></div><RunTicks slots={library.slots.filter((slot) => slot.model.id === model.id)} /><div className="model-counts">{[{ key: 'succeeded', color: 'success', label: '已产出' }, { key: 'active', color: 'active', label: '进行中' }, { key: 'failed', color: 'failed', label: '失败' }, { key: 'waiting', color: 'waiting', label: '等待' }].map(({ key, color, label }) => <span key={key} title={`${label}：${knownRuns ? modelStats[key] : '记录未同步'}`}><i className={`dot ${color}`} />{knownRuns ? modelStats[key] : '—'}</span>)}</div></article>;
      })}</div> : <div className="model-progress-empty"><span className="model-empty-icon"><Layers3 size={20} strokeWidth={1.5} /></span><div><strong>{live.loading ? '正在读取模型目录' : live.catalog ? '目录中暂未配置模型' : '等待模型目录连接'}</strong><span>运行统计只来自真实数据，不预填任何结果。</span></div><span className="model-empty-label">题目目录 · 实时</span></div>}
      <div className="archive-note"><Check size={13} /><span>所有重复运行均保留，不挑选“最佳结果”。失败与等待同样公开。</span></div>
      {thinkingPolicy && <div className="data-notice thinking-policy-notice"><div><strong>思考档位调整 · max → high</strong><p>Astra 与 Sol 在 {new Date(thinkingPolicy.changed_at).toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' })}（北京时间）之后尚未启动的实验统一使用 high。已开始的 max 样本原样保留；每次运行显示各自档位。</p><a href="/api/execution-changes" target="_blank" rel="noreferrer">查看切换记录 ↗</a></div></div>}
    </section>
  </>;
}
