import { useEffect, useRef, useState } from 'react';
import { ArrowUpRight, Check, Columns2, Eye, EyeOff, Maximize2, Minimize2, Pause, Play, RotateCcw, VolumeX, X } from 'lucide-react';
import { caseKey, formatDuration, formatTime, resultPath, trackLabel } from '../lib/data.js';
import { CloseButton, Dialog, EmptyState, Placeholder, StatusBadge, Thumbnail } from './Common.jsx';

export function ComparisonBasket({ entries, onRemove, onClear, onOpen }) {
  if (!entries.length) return null;
  return <aside className="comparison-basket" aria-label="已选择的结果对比篮"><div className="basket-title"><span className="basket-icon"><Columns2 size={19} /></span><div><strong>结果对比 <small>{entries.length} / 4</small></strong><span>{entries.length < 2 ? '再选一个，开始并排观察' : '全部保留，横向看见差异'}</span></div></div><div className="basket-items">{entries.map(({ slot, alias }) => <div className="basket-item" key={slot.id}><div className="basket-thumbnail"><Thumbnail slot={slot} task={slot.task} compact /><span>{alias}</span></div><div className="basket-item-label"><strong>{slot.model.label || slot.model.id}</strong><span title={slot.task.title}>{slot.task.title} · 第 {slot.number} 次</span></div><button className="basket-remove" onClick={() => onRemove(slot.id)} aria-label={`移出 ${slot.model.label || slot.model.id} Run ${slot.number}`} title="移出对比"><X size={13} /></button></div>)}</div><div className="basket-actions"><button className="button small ghost basket-clear" onClick={onClear} title="清空全部已选结果">清空</button><button className="button primary" onClick={onOpen} disabled={entries.length < 2} title={entries.length < 2 ? '至少选择 2 个真实运行记录' : '打开并排对比'}>开始对比<ArrowUpRight size={16} /></button></div></aside>;
}

function CompareMedia({ slot, label, videoRef, onLoaded, onTime, onEnded, onFailure }) {
  const screenshot = resultPath(slot.run?.screenshot_path);
  const video = resultPath(slot.run?.video_path);
  const [broken, setBroken] = useState(false);
  const [videoError, setVideoError] = useState(false);
  useEffect(() => { setBroken(false); setVideoError(false); }, [screenshot, video]);
  if (video && !videoError) return <video ref={videoRef} src={video} poster={screenshot && !broken ? screenshot : undefined} playsInline muted preload="metadata" aria-label={`${label}，${slot.task.title} 的真实视频`} onLoadedMetadata={onLoaded} onDurationChange={onLoaded} onTimeUpdate={onTime} onEnded={onEnded} onError={() => { setVideoError(true); onFailure(); }} />;
  if (screenshot && !broken) return <img src={screenshot} alt={`${label}，${slot.task.title} 的真实截图`} onError={() => setBroken(true)} />;
  return <Placeholder task={slot.task} status={slot.status} run={slot.run} broken={broken || videoError} />;
}

export default function ComparisonDialog({ entries, onClose, onResult }) {
  const [blind, setBlind] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [position, setPosition] = useState(0);
  const [durations, setDurations] = useState({});
  const [playError, setPlayError] = useState('');
  const [failedIds, setFailedIds] = useState(new Set());
  const [playbackRate, setPlaybackRate] = useState(1);
  const [audioId, setAudioId] = useState('none');
  const videos = useRef(new Map());
  const alive = useRef(true);
  const playAttempt = useRef(0);
  const videoEntries = entries.filter(({ slot }) => resultPath(slot.run?.video_path) && !failedIds.has(slot.id));
  const leader = videoEntries[0]?.slot.id;
  const lengthValues = videoEntries.map(({ slot }) => durations[slot.id]).filter((value) => Number.isFinite(value) && value > 0);
  const duration = lengthValues.length ? Math.min(...lengthValues) : 0;
  const differentTasks = new Set(entries.map(({ slot }) => caseKey(slot.task))).size > 1;

  useEffect(() => {
    videos.current.forEach((video, id) => {
      if (!video) return;
      video.playbackRate = playbackRate;
      video.muted = id !== audioId;
    });
  }, [playbackRate, audioId, entries]);

  useEffect(() => {
    alive.current = true;
    const refs = videos.current;
    return () => {
      alive.current = false;
      playAttempt.current++;
      refs.forEach((video) => video?.pause());
    };
  }, []);

  const pauseAll = () => {
    playAttempt.current++;
    videos.current.forEach((video) => video?.pause());
    setPlaying(false);
  };
  const seekAll = (value) => {
    const time = Math.max(0, Number(value));
    videos.current.forEach((video) => {
      if (!video || !Number.isFinite(video.duration)) return;
      try { video.currentTime = Math.min(time, video.duration); } catch { /* Media is not ready yet. */ }
    });
    setPosition(time);
  };
  const togglePlay = async () => {
    if (playing) { pauseAll(); return; }
    const refs = [...videos.current.values()].filter(Boolean);
    if (!refs.length) { setPlayError('视频尚未就绪，请稍后重试。'); return; }
    setPlayError('');
    const attempt = ++playAttempt.current;
    if (duration && position >= duration - 0.1) seekAll(0);
    else seekAll(position);
    const results = await Promise.allSettled(refs.map((video) => Promise.resolve().then(() => video.play())));
    if (!alive.current || attempt !== playAttempt.current) { refs.forEach((video) => video.pause()); return; }
    if (results.some((result) => result.status === 'rejected')) {
      refs.forEach((video) => video.pause());
      setPlaying(false);
      setPlayError('部分视频无法播放，已暂停全部视频。请重试，或在结果详情中打开原文件。');
    } else setPlaying(true);
  };
  const timeUpdate = (id) => {
    const first = videos.current.get(id);
    if (id !== leader || !first) return;
    setPosition(first.currentTime);
    if (playing) videos.current.forEach((video, otherId) => {
      if (otherId === id || !video || !Number.isFinite(video.duration)) return;
      if (Math.abs(video.currentTime - first.currentTime) > 0.4) {
        try { video.currentTime = Math.min(first.currentTime, video.duration); } catch { /* Wait for metadata. */ }
      }
    });
  };
  const metadataLoaded = (id, event) => {
    const value = event.currentTarget.duration;
    if (Number.isFinite(value) && value > 0) setDurations((previous) => previous[id] === value ? previous : { ...previous, [id]: value });
  };

  return <Dialog onClose={onClose} title="真实结果并排对比" className={`comparison-dialog ${expanded ? 'comparison-fullscreen' : ''}`}>
    <div className="comparison-header"><div><div className="eyebrow"><span className="red-label">并排对比</span><span>{differentTasks ? '跨题目对比' : '独立运行对比'}</span></div><h2>让差异，一眼可见。<span>{entries.length} 个真实运行</span></h2></div><div className="comparison-header-actions"><button className={`blind-toggle ${blind ? 'active' : ''}`} onClick={() => setBlind((value) => !value)} aria-pressed={blind} title={blind ? '退出盲看，显示模型名称' : '隐藏模型名称，使用稳定的 A/B/C/D 标识'}>{blind ? <EyeOff size={16} /> : <Eye size={16} />}盲看模式<span className="switch-track"><i /></span></button><button className="icon-button" onClick={() => setExpanded((value) => !value)} title={expanded ? '退出全屏布局' : '全屏对比'} aria-label={expanded ? '退出全屏布局' : '全屏对比'}>{expanded ? <Minimize2 size={18} /> : <Maximize2 size={18} />}</button><CloseButton onClick={onClose} /></div></div>
    <div className="comparison-body">
      {entries.length < 2 ? <EmptyState icon={Columns2} title="选两个结果，再看一遍" description="在任务矩阵或结果详情中点击「加入对比」。支持 2–4 个真实运行，也可以跨题目选择。"><button className="button primary" onClick={onClose} title="返回作品库选择结果">去选择结果<ArrowUpRight size={15} /></button></EmptyState>
        : <><div className="comparison-notice"><span>{blind ? <><EyeOff size={14} />模型身份已隐藏。匿名标识在本次选择期间保持不变。</> : <><Check size={14} />按选择顺序并排展示，没有排名，不产生分数。</>}</span>{differentTasks && <strong>不同任务 · 请留意各列题目</strong>}</div><div className="comparison-columns" style={{ '--compare-columns': entries.length }}>{entries.map(({ slot, alias }) => {
          const name = blind ? `结果 ${alias}` : slot.model.label || slot.model.id;
          return <article className="comparison-column" key={slot.id}><div className="compare-column-heading"><span className="anonymous-label">{alias}</span><div><h3>{name}</h3><span>第 {slot.number} 次{!blind && ` · 思考 ${slot.run?.thinking_requested || '未知'}`}</span></div><StatusBadge status={slot.status} small /></div><div className="compare-task-label"><span>{trackLabel(slot.task.track)} / {slot.task.case_id || slot.task.id}</span><strong title={slot.task.title}>{slot.task.title}</strong></div><div className="compare-stage"><CompareMedia slot={slot} label={`结果 ${alias}`} videoRef={(video) => { if (video) { videos.current.set(slot.id, video); video.playbackRate = playbackRate; video.muted = slot.id !== audioId; } else videos.current.delete(slot.id); }} onLoaded={(event) => metadataLoaded(slot.id, event)} onTime={() => timeUpdate(slot.id)} onEnded={pauseAll} onFailure={() => { setFailedIds((previous) => new Set([...previous, slot.id])); pauseAll(); setPlayError('有视频无法读取，已暂停同步播放。可以在详情中检查原始文件。'); }} /></div><div className="compare-column-footer"><span>运行耗时 <strong>{formatDuration(slot.run?.duration_ms)}</strong></span><button className="button small ghost" onClick={() => { pauseAll(); onResult(slot); }} disabled={blind} title={blind ? '退出盲看模式后可打开包含模型身份的详情' : '查看原始结果详情'}>查看详情<ArrowUpRight size={13} /></button></div></article>;
        })}</div></>}
      {entries.length >= 2 && videoEntries.length > 0 && <div className="sync-player"><div className="sync-heading"><span><Columns2 size={14} />视频同步控制<small>{videoEntries.length} 个视频</small></span><span><VolumeX size={13} />{audioId === 'none' ? '静音并排播放' : '单路试听'}</span></div><div className="sync-options"><label>播放速度 <select aria-label="同步播放速度" value={playbackRate} onChange={(event) => setPlaybackRate(Number(event.target.value))}><option value={0.25}>0.25×</option><option value={0.5}>0.5×</option><option value={1}>1×</option><option value={1.5}>1.5×</option></select></label><label>声音 <select aria-label="选择单路试听" value={audioId} onChange={(event) => setAudioId(event.target.value)}><option value="none">全部静音</option>{videoEntries.map(({ slot, alias }) => <option key={slot.id} value={slot.id}>{blind ? `结果 ${alias}` : `${slot.model.label || slot.model.id} · R${slot.number}`}</option>)}</select></label></div><div className="sync-controls"><button className="sync-play" onClick={togglePlay} title={playing ? '同步暂停全部视频' : '同步播放全部视频'} aria-label={playing ? '同步暂停全部视频' : '同步播放全部视频'}>{playing ? <Pause size={19} fill="currentColor" /> : <Play size={19} fill="currentColor" />}</button><button className="icon-button" onClick={() => { pauseAll(); seekAll(0); }} title="全部视频回到起点" aria-label="全部视频回到起点"><RotateCcw size={17} /></button><span className="sync-time">{formatTime(position)}</span><input type="range" min="0" max={duration || 1} step="0.05" value={Math.min(position, duration || 1)} disabled={!duration} onChange={(event) => seekAll(event.target.value)} aria-label="同步定位所有视频" title="统一拖动时间轴；以最短视频时长为范围" /><span className="sync-time">{formatTime(duration)}</span></div>{playError && <p className="sync-error" role="status">{playError}</p>}<p className="sync-note">一起播放、暂停或拖动时间轴。以已加载视频中最短时长为范围。</p></div>}
    </div><div className="comparison-footer"><span>观察结果，不评价胜负。</span><span>{blind ? '盲看 · 身份已隐藏' : '公开视图 · 全部可见'}</span></div>
  </Dialog>;
}
