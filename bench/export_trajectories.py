"""Export completed pi sessions to downloadable native JSONL and offline HTML."""
import argparse
import json
import shutil
import subprocess
import time
import uuid
from common import ROOT, atomic_json, now, public_path, sha256

def read_record(path):
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def export_session(src, number, target):
    """Keep each JSONL snapshot and its HTML provenance independently recoverable."""
    dst = target / f'session-{number}.jsonl'
    html = target / f'session-{number}.html'
    state_path = target / f'session-{number}.export.json'
    state = read_record(state_path)
    token = uuid.uuid4().hex
    snapshot = target / f'.session-{number}.{token}.jsonl'
    temporary_html = target / f'.session-{number}.{token}.html'
    trace = {'number': number, 'source_session': src.name, 'jsonl_path': None,
             'html_path': None, 'sha256': None, 'size_bytes': None,
             'html_source_sha256': state.get('html_source_sha256'), 'export_error': None}
    fingerprint = None
    try:
        fingerprint = sha256(src)
        if not dst.is_file() or sha256(dst) != fingerprint:
            shutil.copy2(src, snapshot)
            # Hash the actual snapshot in case the source changed while copied.
            fingerprint = sha256(snapshot)
            snapshot.replace(dst)
        trace.update(jsonl_path=public_path(dst), sha256=fingerprint, size_bytes=dst.stat().st_size)
        html_current = (html.is_file() and html.stat().st_size > 0
                        and state.get('html_source_sha256') == fingerprint
                        and state.get('html_sha256') == sha256(html))
        if not html_current:
            result = subprocess.run(
                ['pi', '--offline', '--no-extensions', '--no-skills', '--export', str(dst), str(temporary_html)],
                capture_output=True, text=True, timeout=60)
            if result.returncode or not temporary_html.is_file() or not temporary_html.stat().st_size:
                raise RuntimeError(f'pi --export exited {result.returncode}: {result.stderr[-1000:]}')
            temporary_html.replace(html)
            state.update(html_source_sha256=fingerprint, html_sha256=sha256(html), exported_at=now())
        state.update(source_session=src.name, jsonl_sha256=fingerprint, checked_at=now(), export_error=None)
        atomic_json(state_path, state)
        trace.update(html_path=public_path(html), html_source_sha256=fingerprint)
    except Exception as error:
        # An old HTML file may remain on disk, but it is never linked as the
        # current transcript unless its recorded source hash matches this JSONL.
        trace['export_error'] = {'type': type(error).__name__, 'message': str(error)[-1400:], 'at': now()}
        state.update(source_session=src.name, jsonl_sha256=fingerprint,
                     checked_at=now(), export_error=trace['export_error'])
        try:
            atomic_json(state_path, state)
        except OSError:
            pass
    finally:
        for temporary in (snapshot, temporary_html):
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
    return trace


def export_all():
    # Retain prior exports when one run cannot be read or is being resumed.
    catalog = read_record(ROOT/'data/trajectories.json').get('runs', {})
    errors = []
    for meta in sorted((ROOT/'runs').glob('*/*/*/run-*/run.json')):
        try:
            d = json.loads(meta.read_text())
            if d['status'] in {'queued','generating','running','interrupted'}: continue
            sessions = sorted((meta.parent/'private/sessions').glob('*.jsonl'))
            if not sessions: continue
            target = meta.parent/'trajectory'; target.mkdir(exist_ok=True)
            traces = [export_session(src, n, target) for n, src in enumerate(sessions, 1)]
            record = {'run_id':d['id'],'trajectory_path':traces[-1]['jsonl_path'],'trajectory_html_path':traces[-1]['html_path'],
                      'sessions':traces,'exported_at':now(),'format':'pi native session JSONL + pi --export self-contained HTML',
                      'scope':'Complete native model run transcript, tool calls/results, messages and settings; source session preserved unchanged.'}
            atomic_json(target/'index.json',record)
            catalog[d['id']] = record
        except Exception as error:
            errors.append({'metadata_path': str(meta.relative_to(ROOT)),
                           'type': type(error).__name__, 'message': str(error)[-1400:]})
    atomic_json(ROOT/'data/trajectories.json',{'updated_at':now(),'runs':catalog,'errors':errors})
    return len(catalog)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--watch',action='store_true');a=p.parse_args()
    while True:
        try: print(json.dumps({'exported_runs':export_all(),'at':now()}),flush=True)
        except Exception as e: print(json.dumps({'error':str(e)}),flush=True)
        if not a.watch: break
        time.sleep(20)
