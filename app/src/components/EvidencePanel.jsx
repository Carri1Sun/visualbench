import { AlertCircle, CheckCircle2, CircleHelp, ShieldCheck } from 'lucide-react';
import { asText } from '../lib/data.js';

export default function EvidencePanel({ run }) {
  const checks = run?.technical_checks;
  const audit = run?.audit;
  const changed = audit?.immutable_input_changes || [];
  const usage = audit?.usage_observations;
  return <div className="evidence-panel">
    <h3><ShieldCheck size={17} />技术检查与输入追溯</h3>
    <p>这些记录说明采集过程和输入一致性，作品的视觉表现由观看者自行观察。</p>
    <div className="evidence-facts">
      <div><span>媒体采集</span><strong>{run?.render_outcome === 'completed' ? '采集结束' : run?.render_outcome === 'partial' ? '部分产物可用' : run?.render_outcome || '尚无记录'}</strong></div>
      <div><span>浏览器技术检查</span><strong>{checks?.technical_pass === true ? <><CheckCircle2 size={13} />已通过记录中的检查</> : checks?.technical_pass === false ? <><AlertCircle size={13} />发现问题</> : '尚无记录'}</strong></div>
      <div><span>输入文件一致性{audit?.provisional ? ' · 暂存检查' : ''}</span><strong>{audit?.immutable_input_check ? `${audit.immutable_input_check.checked_file_count} 个文件 · ${audit.immutable_input_check.all_match ? '校验一致' : '发现变化'}` : '尚未校验'}</strong></div>
      <div><span>预设交互动作</span><strong>{checks?.interaction_actions?.status === 'not_performed' ? <><CircleHelp size={13} />尚未执行</> : checks?.interaction_actions?.status || '尚无记录'}</strong></div>
    </div>
    {checks?.interaction_actions?.status === 'not_performed' && <p className="evidence-notice">当前录屏观察页面初始状态。题目中的点击、拖动等交互动作尚未验证。</p>}
    {changed.length > 0 && <div className="record-error"><strong>检测到输入文件变化</strong><pre>{asText(changed)}</pre></div>}
    {checks?.errors?.length > 0 && <div className="record-error"><strong>技术检查错误</strong><pre>{asText(checks.errors)}</pre></div>}
    {usage && <div className="evidence-usage"><span>模型回复 {usage.model_response_count ?? '—'} 次</span><span>工具调用 {usage.tool_call_count ?? '—'} 次</span><span>推理 tokens：{usage.reasoning_tokens ?? '未提供'}</span>{usage.provider_reported_cost_usd != null && <span title={usage.cost_note || 'Pi / provider 报告的目录估算，非实际账单'}>目录估算成本 ${Number(usage.provider_reported_cost_usd).toFixed(4)}</span>}</div>}
    {checks && <details className="evidence-raw"><summary>查看完整技术检查记录</summary><pre>{asText(checks)}</pre></details>}
    {audit && <details className="evidence-raw"><summary>查看完整输入追溯记录</summary><pre>{asText(audit)}</pre></details>}
  </div>;
}
