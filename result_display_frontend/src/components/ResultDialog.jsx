import { useEffect, useState } from 'react';
import { AlertCircle, ArrowUpRight, Check, Code2, Columns2, Download, ExternalLink, FileText, Image, Info, List, MessageSquareText, MonitorPlay, Play, Plus } from 'lucide-react';
import { artifactUrl, asText, formatDate, formatDuration, resultPath, sourcePath, statusInfo, trackLabel } from '../lib/data.js';
import useTextFile from '../hooks/useTextFile.js';
import TrajectoryPanel from './TrajectoryPanel.jsx';
import EvidencePanel from './EvidencePanel.jsx';
import { ObservationPanel, ObservationBadge } from './Observations.jsx';
import { CloseButton, Dialog, EmptyState, FileContent, ModelMark, Placeholder, StatusBadge, TextBlock, Thumbnail } from './Common.jsx';

const TABS = [
  { id: 'visual', label: '画面', icon: Image },
  { id: 'plan', label: '公开方案', icon: FileText },
  { id: 'prompt', label: '完整 Prompt', icon: MessageSquareText },
  { id: 'code', label: '代码', icon: Code2 },
  { id: 'records', label: '运行记录', icon: List },
];

function PicturePanel({ slot }) {
  const { task, run } = slot;
  const screenshot = resultPath(run?.screenshot_path);
  const video = resultPath(run?.video_path);
  const preview = artifactUrl(run?.artifact_path);
  const previewIsolated = preview && new URL(preview).origin !== window.location.origin;
  const [mode, setMode] = useState(video ? 'video' : 'screenshot');
  const [videoError, setVideoError] = useState(false);
  useEffect(() => setVideoError(false), [video]);
  return <div className="picture-panel"><div className="picture-toolbar"><div className="view-switch" role="group" aria-label="画面查看方式"><button className={mode === 'screenshot' ? 'active' : ''} onClick={() => setMode('screenshot')} title="查看真实截图"><Image size={14} />截图</button>{video && <button className={mode === 'video' ? 'active' : ''} onClick={() => setMode('video')} title="播放真实输出视频"><Play size={14} />视频</button>}{task.track === 'frontend' && preview && previewIsolated && <button className={mode === 'preview' ? 'active' : ''} onClick={() => setMode('preview')} title="在隔离的 iframe 中加载独立产物"><MonitorPlay size={14} />交互预览</button>}</div><div className="file-actions">{(mode === 'video' ? video : screenshot) && mode !== 'preview' && <a className="button small ghost" href={mode === 'video' ? video : screenshot} download target="_blank" rel="noreferrer" title="下载真实输出文件"><Download size={14} />下载{mode === 'video' ? '视频' : '截图'}</a>}{preview && <a className="button small ghost" href={preview} target="_blank" rel="noreferrer" title="在独立页面打开产物"><ExternalLink size={14} />独立预览</a>}</div></div>
    <div className={`result-stage ${mode === 'preview' ? 'iframe-stage' : ''}`}>
      {mode === 'preview' && preview && previewIsolated ? <iframe title={`${task.title} 的隔离交互预览`} src={preview} sandbox="allow-scripts allow-same-origin" referrerPolicy="no-referrer" loading="lazy" style={{ aspectRatio: `${task.width || 1440} / ${task.height || 900}` }} />
        : mode === 'video' && video ? videoError ? <EmptyState icon={AlertCircle} title="视频暂时无法播放" description="原始视频可能尚未写入完成，或浏览器不支持其编码。可下载文件查看。" /> : <video key={video} src={video} poster={screenshot || undefined} controls playsInline preload="metadata" onError={() => setVideoError(true)} aria-label={`${task.title} 的真实输出视频`} />
        : screenshot ? <Thumbnail slot={slot} task={task} /> : <Placeholder task={task} status={slot.status} run={run} />}
    </div>
    {preview && !previewIsolated && <p className="evidence-notice">请通过 127.0.0.1:4173 打开展示站以使用隔离交互预览，也可点击独立预览。</p>}<div className="visual-note"><Info size={14} /><span>{mode === 'preview' ? '交互预览在独立站点中运行，可以直接操作页面控件。' : '只展示结果索引提供的真实产物。没有截图时保留占位，不用输入素材替代。'}</span></div>
  </div>;
}

export default function ResultDialog({ slot, selected, onClose, onSelect }) {
  const [tab, setTab] = useState('visual');
  const run = slot.run;
  const code = sourcePath(run);
  const plan = useTextFile(run?.plan_path, tab === 'plan');
  const request = useTextFile(run?.request_path, tab === 'prompt');
  const source = useTextFile(code, tab === 'code');
  const metadata = useTextFile(run?.metadata_path, tab === 'records');
  const consoleLog = useTextFile(run?.console_path, tab === 'records');
  const failed = statusInfo(slot.status).group === 'failed';
  return <Dialog onClose={onClose} title={`${slot.task.title} · ${slot.model.label || slot.model.id} · Run ${slot.number}`} className="result-dialog">
    <div className="result-dialog-header"><div className="result-dialog-title"><div className="eyebrow"><span className="red-label">RUN ARCHIVE</span><span>{trackLabel(slot.task.track)} / {slot.task.case_id || slot.task.id}</span></div><h2>{slot.task.title}</h2><div className="result-identity"><ModelMark model={slot.model} small /><strong>{slot.model.label || slot.model.id}</strong><span className="identity-divider" /><span>Run {slot.number}</span><span>思考：{run?.thinking_requested || '未知'}</span><StatusBadge status={slot.status} small /><ObservationBadge runId={run?.id} /><span className="detail-duration">{formatDuration(run?.duration_ms)}</span></div></div><div className="dialog-header-actions"><button className={`button small ${selected ? 'selected-button' : 'outline'}`} onClick={() => onSelect(slot)} disabled={!run} aria-pressed={selected} title={run ? selected ? '将此结果移出对比篮' : '将此结果加入对比篮，最多 4 个' : '尚无真实运行记录，暂不能选择对比'}>{selected ? <Check size={15} /> : <Columns2 size={15} />}{selected ? '已加入对比' : '加入对比'}</button><CloseButton onClick={onClose} /></div></div>
    {failed && <div className="result-failure-banner"><AlertCircle size={17} /><div><strong>{statusInfo(slot.status).label}，记录仍然保留。</strong><p>{asText(run?.error) || '结果索引未附带具体错误。可查看源码、元数据与控制台记录。'}</p></div></div>}
    {run && <TrajectoryPanel run={run} />}
    {run && <ObservationPanel runId={run.id} />}
    {run?.technical_checks?.technical_pass === false && <div className="technical-warning"><AlertCircle size={15} />已有真实产物；技术检查发现问题，详情见运行记录。</div>}
    <div className="detail-tabs" role="tablist" aria-label="结果详情栏目">{TABS.map(({ id, label, icon: Icon }) => <button key={id} id={`detail-tab-${id}`} role="tab" aria-selected={tab === id} aria-controls={`detail-panel-${id}`} className={tab === id ? 'active' : ''} onClick={() => setTab(id)} title={`查看${label}`}><Icon size={16} />{label}{id === 'plan' && resultPath(run?.plan_path) && <i className="tab-file-dot" />}</button>)}</div>
    <div className="result-dialog-body" id={`detail-panel-${tab}`} role="tabpanel" aria-labelledby={`detail-tab-${tab}`}>
      {tab === 'visual' && <PicturePanel slot={slot} />}
      {tab === 'plan' && <><div className="panel-introduction"><span className="panel-icon"><FileText size={21} /></span><div><h3>模型提交的公开方案</h3><p>公开方案涵盖布局、视觉方向、交互与实现选择。</p></div></div><FileContent resource={plan} path={run?.plan_path} emptyTitle="尚无公开方案文件" emptyDescription={run ? '此运行的索引尚未提供 plan_path。若模型提交方案，原文件将在此展示。' : '等待真实运行记录与模型提交的公开方案。'} /></>}
      {tab === 'prompt' && <><div className="panel-introduction"><span className="panel-icon"><MessageSquareText size={21} /></span><div><h3>完整任务输入</h3><p>来自 catalog 的原文。原始输入可追溯，不改写、不补全。</p></div></div>{slot.task.prompt ? <TextBlock text={asText(slot.task.prompt)} title="Catalog / Prompt" filename={`${slot.task.case_id || 'task'}-prompt.txt`} /> : <EmptyState compact title="目录未提供 Prompt 原文" description="任务输入到达后将自动显示。" />}{resultPath(run?.request_path) && <section className="record-section"><h3>本次运行的实际请求</h3><FileContent resource={request} path={run.request_path} /></section>}</>}
      {tab === 'code' && <><div className="panel-introduction"><span className="panel-icon"><Code2 size={21} /></span><div><h3>结果源码</h3><p>{run?.code_path ? '读取索引中的 code_path，只展示文本，不执行代码。' : code ? '索引未附带 code_path，使用 HTML 产物作为源码回退。' : '保留模型写出的源码，失败的运行同样可以查看已有文件。'}</p></div>{code && <a href={artifactUrl(code)} className="button small outline" target="_blank" rel="noreferrer" title="打开原始源码文件">原始文件<ArrowUpRight size={14} /></a>}</div><FileContent resource={source} path={code} emptyTitle="尚无可读取的源码文件" emptyDescription="未提供 code_path，也没有可用的 HTML 产物作为回退；不会推测或生成源码。" /></>}
      {tab === 'records' && <><EvidencePanel run={run} /><div className="panel-introduction"><span className="panel-icon"><List size={21} /></span><div><h3>运行记录与错误</h3><p>索引、元数据和控制台文件均为实际记录，不隐藏失败。</p></div></div><dl className="record-summary"><div><dt>状态</dt><dd><StatusBadge status={slot.status} small /></dd></div><div><dt>耗时</dt><dd>{formatDuration(run?.duration_ms)}</dd></div><div><dt>开始</dt><dd>{formatDate(run?.started_at)}</dd></div><div><dt>结束</dt><dd>{formatDate(run?.finished_at)}</dd></div></dl>{run?.error && <section className="record-error"><h3><AlertCircle size={16} />错误信息</h3><pre>{asText(run.error)}</pre></section>}<section className="record-section"><h3>运行与附属归档记录</h3>{run ? <TextBlock text={asText(run)} title="Results / Trajectory / Audit" filename={`${run.id || 'run'}-record.json`.replace(/\//g, '-')} /> : <EmptyState compact title="尚未写入运行记录" description="这是由题目、模型与重复次数推导的计划运行位，正在等待真实输出。" />}</section><section className="record-section"><h3>元数据文件</h3><FileContent resource={metadata} path={run?.metadata_path} emptyTitle="尚无元数据文件" emptyDescription="结果索引未提供 metadata_path。上方仍可查看实际索引记录。" /></section><section className="record-section"><h3>控制台记录</h3><FileContent resource={consoleLog} path={run?.console_path} emptyTitle="尚无控制台文件" emptyDescription="结果索引未提供 console_path；没有文件不等于没有错误。" /></section></>}
    </div>
    <div className="result-dialog-footer"><span><span className={`dot ${run ? 'success' : 'waiting'}`} />{run ? '真实运行记录 · 文件按需读取' : '计划运行位 · 等待真实记录'}</span><button className="button small ghost" onClick={onClose} title="关闭结果详情">关闭详情<ArrowUpRight size={13} /></button></div>
  </Dialog>;
}
