import { Download, ExternalLink, GitBranch, Route } from 'lucide-react';
import { artifactUrl, formatDate, resultPath } from '../lib/data.js';

export default function TrajectoryPanel({ run }) {
  const jsonl = resultPath(run?.trajectory_path);
  const html = resultPath(run?.trajectory_html_path);
  const attempts = Array.isArray(run?.attempts) ? run.attempts : [];
  const sessions = Array.isArray(run?.sessions) ? run.sessions : [];
  const downloadName = (path, fallback) => `${(run?.id || 'visualbench-run').replace(/[^a-zA-Z0-9._-]/g, '-')}-${path?.split('/').pop() || fallback}`;
  const continuations = attempts.filter((attempt) => /continu|resume/i.test(`${attempt.reason || ''} ${attempt.type || ''}`)).length;
  return <section className="trajectory-panel" aria-label="完整运行轨迹">
    <div className="trajectory-heading"><div><Route size={19} /><strong>完整运行轨迹</strong></div><span>{attempts.length} 次尝试 · {continuations} 次续跑</span></div>
    <p>保存 Pi 原生会话，包含模型消息、工具调用与返回内容。每次尝试均可追溯。</p>
    <div className="trajectory-actions">
      {jsonl ? <a className="button outline small" href={jsonl} download={downloadName(jsonl, 'trajectory.jsonl')}><Download size={15} />下载运行轨迹 JSONL</a> : <span className="trajectory-pending">JSONL 轨迹尚未归档</span>}
      {html && <a className="button outline small" href={html} download={downloadName(html, 'trajectory.html')}><Download size={15} />下载离线轨迹 HTML</a>}
      {html && <a className="button ghost small" href={artifactUrl(html)} target="_blank" rel="noreferrer"><ExternalLink size={15} />新窗口查看轨迹</a>}
    </div>
    {sessions.length > 1 && <details className="trajectory-sessions"><summary><GitBranch size={14} />全部 {sessions.length} 个原生会话</summary><div>{sessions.map((session, index) => <div className="trajectory-session" key={session.jsonl_path || index}><span>会话 {session.number || index + 1}</span><span>{session.size_bytes ? `${(session.size_bytes / 1024).toFixed(1)} KB` : ''}</span>{resultPath(session.jsonl_path) && <a href={session.jsonl_path} download={downloadName(session.jsonl_path, 'trajectory.jsonl')}>下载 JSONL</a>}{resultPath(session.html_path) && <a href={session.html_path} download={downloadName(session.html_path, 'trajectory.html')}>下载 HTML</a>}</div>)}</div></details>}
    {attempts.length > 0 && <details className="trajectory-sessions"><summary>尝试与续跑记录</summary><div>{attempts.map((attempt, index) => <div className="trajectory-attempt" key={`${index}-${attempt.started_at}`}><strong>#{attempt.number || index + 1} · {attempt.reason === 'initial' ? '首次生成' : /continu|resume/i.test(attempt.reason || '') ? '继续执行' : attempt.reason || '运行尝试'}</strong><span>{formatDate(attempt.started_at)}</span>{attempt.error && <p>{typeof attempt.error === 'string' ? attempt.error : JSON.stringify(attempt.error)}</p>}</div>)}</div></details>}
  </section>;
}
