import { createContext, useContext, useMemo, useState } from 'react';
import { Download, Flag, Trash2 } from 'lucide-react';
import { downloadText } from '../lib/data.js';

const Context = createContext({ records: {}, save: () => {}, remove: () => {}, error: null, roundId: 'unknown' });
const STORAGE_KEY = 'visualbench.manual-observations.v1';
function readStored() {
  try { const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}'); return value && typeof value === 'object' ? value : {}; } catch { return {}; }
}

export function ObservationProvider({ roundId = 'unknown', children }) {
  const [allRecords, setAllRecords] = useState(readStored);
  const [error, setError] = useState(null);
  const records = useMemo(() => Object.fromEntries(Object.values(allRecords).filter((item) => item?.round_id === roundId && item.run_id).map((item) => [item.run_id, item])), [allRecords, roundId]);
  const persist = (next) => {
    setAllRecords(next);
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)); setError(null); } catch { setError('浏览器未能保存标记，请导出 JSON 留存。'); }
  };
  const save = (runId, note) => {
    const key = `${roundId}::${runId}`;
    const now = new Date().toISOString();
    persist({ ...allRecords, [key]: { run_id: runId, round_id: roundId, kind: 'manual_observation', marked_failed: true, note: note.trim(), created_at: allRecords[key]?.created_at || now, updated_at: now } });
  };
  const remove = (runId) => { const next = { ...allRecords }; delete next[`${roundId}::${runId}`]; persist(next); };
  return <Context.Provider value={{ records, save, remove, error, roundId }}>{children}</Context.Provider>;
}

export function useObservations() { return useContext(Context); }

export function ObservationBadge({ runId }) {
  const { records } = useObservations();
  return records[runId]?.marked_failed ? <span className="observation-badge" title={records[runId].note || '本地人工观察记录'}><Flag size={11} />人工标记失败</span> : null;
}

export function ObservationPanel({ runId }) {
  const { records, save, remove, error, roundId } = useObservations();
  const record = records[runId];
  const [editing, setEditing] = useState(false);
  const [note, setNote] = useState(record?.note || '');
  if (!runId) return null;
  const exportRecords = () => downloadText(JSON.stringify({ schema_version: '1.0', round_id: roundId, exported_at: new Date().toISOString(), type: 'manual_observations', records: Object.values(records) }, null, 2), `visualbench-observations-${roundId}.json`, 'application/json');
  return <section className="observation-panel" aria-label="人工观察标记">
    <div className="observation-heading"><strong><Flag size={15} />人工观察</strong><span>保存在此浏览器，原始作品持续展示</span></div>
    <div className="observation-actions"><button className={`button small ${record ? 'selected-button' : 'outline'}`} onClick={() => { if (!record) save(runId, note); setEditing(true); }}><Flag size={14} />{record ? '已标记失败 · 编辑备注' : '标记失败'}</button>{record && <button className="button small ghost" onClick={() => { remove(runId); setNote(''); setEditing(false); }}><Trash2 size={14} />撤销标记</button>}<button className="button small ghost" onClick={exportRecords} disabled={!Object.keys(records).length}><Download size={14} />导出人工标记 JSON{Object.keys(records).length ? ` (${Object.keys(records).length})` : ''}</button></div>
    {record?.note && !editing && <p className="observation-note">{record.note}</p>}
    {editing && <div className="observation-editor"><label htmlFor="observation-note">自由备注（可选）</label><textarea id="observation-note" value={note} onChange={(event) => setNote(event.target.value)} placeholder="记录你看到的问题或失败原因…" rows={3} /><button className="button small outline" onClick={() => { save(runId, note); setEditing(false); }}>保存备注</button></div>}
    {error && <p className="observation-error" role="status">{error}</p>}
  </section>;
}
