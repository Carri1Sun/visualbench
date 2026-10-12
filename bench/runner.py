"""Resumable pi evaluation queue. All model artifacts remain untouched by the curator."""
import argparse
import concurrent.futures
import fcntl
import json
import os
import platform
import queue
import signal
import shlex
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from common import ROOT, CONFIG, PACKS, all_cases, atomic_json, init, now, protocol, public_path, publish, sha256

STATE_LOCK = threading.RLock()
RENDER_QUEUE = queue.Queue()
STOP = threading.Event()
CASES = {(t, c['id']): c for t, c in all_cases()}
PID_BY_SESSION = {}

POLICY = '''你在执行独立的固定输入评测。仅处理当前工作目录内这一题。
先阅读题目，写公开设计方案，然后完成所有源码和交付，不要等待用户确认。
不得读取其他运行、父目录题库、来源网站、原作者答案、用户文件或认证信息。
不得修改输入文件、vendor、case.config.json、package.json、package-lock.json 或 node_modules；不得安装额外依赖、调用其他模型、下载素材或访问外部网络。
可使用 read、write、edit、bash，在当前目录内编写和运行代码。不要读取环境变量、访问账户/凭据或启动后台常驻进程。
视频依赖已统一预装，跳过 npm ci。可运行 npm run typecheck；视频渲染须加 --concurrency=1，保留原始尺寸和完整时长。外部捕获器也将验证并补充缺失的媒体导出。
45分钟为本次agent会话总时限，内部调试包含在同一次运行内。优先实现完整任务，不要擅自简化时长、帧率或输入。
所有创意和代码由你独立完成，最终回复简短列出真实产物与未解决事项。
'''

def update(meta, **changes):
    with STATE_LOCK:
        d = json.loads(meta.read_text()); d.update(changes); d['updated_at'] = now()
        atomic_json(meta, d); publish()
        return d

def run_command(cmd, cwd, stdout, stderr, timeout, on_start=None):
    start = time.monotonic()
    with open(stdout, 'wb') as out, open(stderr, 'wb') as err:
        process = subprocess.Popen(cmd, cwd=cwd, stdout=out, stderr=err, start_new_session=True,
                                   env={**os.environ, 'PI_OFFLINE': '1', 'NO_COLOR': '1'})
        if on_start: on_start(process.pid)
        while process.poll() is None:
            if STOP.is_set() or time.monotonic() - start > timeout:
                try: os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError: pass
                try: process.wait(10)
                except subprocess.TimeoutExpired:
                    try: os.killpg(process.pid, signal.SIGKILL)
                    except ProcessLookupError: pass
                return -15 if STOP.is_set() else -124, round((time.monotonic()-start)*1000)
            time.sleep(1)
        return process.returncode, round((time.monotonic()-start)*1000)

def prepare(meta):
    d = json.loads(meta.read_text()); work = meta.parent / 'work'; private = meta.parent / 'private'
    private.mkdir(exist_ok=True)
    if not work.exists():
        if d['track'] == 'frontend':
            cmd = ['python3', str(PACKS['frontend']/'scripts/prepare_case.py'), d['case_id'], '--dest', str(work), '--lang', 'zh', '--variant', 'full']
        else:
            cmd = ['python3', str(PACKS['video']/'scripts/prepare_case.py'), d['case_id'], str(work), '--language', 'zh']
        result = subprocess.run(cmd, capture_output=True, text=True)
        (private/'prepare.log').write_text(result.stdout + result.stderr)
        if result.returncode: raise RuntimeError('Input preparation failed: '+result.stderr[-500:])
    if d['track'] == 'video' and not (work/'node_modules').exists():
        (work/'node_modules').symlink_to(ROOT/'.runtime/remotion/node_modules', target_is_directory=True)
    if d['track'] == 'video' and not (work/'.remotion').exists():
        (work/'.remotion').symlink_to(ROOT/'.remotion', target_is_directory=True)
    (private/'policy.txt').write_text(POLICY)
    entry = 'INPUT.zh.txt' if d['track'] == 'frontend' else 'PROMPT.md'
    request = {
        'protocol': protocol(), 'model': d['model'], 'provider': d['provider'], 'thinking': d.get('thinking_requested', 'max'),
        'system_append': POLICY, 'input': (work/entry).read_text(),
        'initial_message': '请完成当前目录中的评测任务，阅读附带的任务要求，实际写入方案和所有源码产物，继续执行到交付完成。',
        'input_sha256': sha256(work/entry),
        'input_files': {str(p.relative_to(work)): sha256(p) for p in work.rglob('*') if p.is_file() and 'node_modules' not in p.parts},
    }
    # Frozen once; resumption does not overwrite the initial request.
    if not (meta.parent/'request.json').exists(): atomic_json(meta.parent/'request.json', request)
    else: request = json.loads((meta.parent/'request.json').read_text())
    return work, private, entry, request

def parse_events(private):
    usage = {'input_tokens': 0, 'output_tokens': 0, 'cache_read_tokens': 0, 'cache_write_tokens': 0, 'total_tokens': 0}
    raw_usage = []; errors = []; effective = None; tool_calls = []; messages = 0
    for log in sorted(private.glob('attempt-*.jsonl')):
        for line in log.open(errors='replace'):
            try: event = json.loads(line)
            except (ValueError, TypeError): continue
            if event.get('type') == 'thinking_level_change': effective = event.get('thinkingLevel')
            if event.get('type') == 'tool_execution_start':
                tool_calls.append({'tool': event.get('toolName'), 'id': event.get('toolCallId')})
            if event.get('type') == 'message_end':
                m = event.get('message', {})
                if m.get('role') == 'assistant':
                    messages += 1
                    if m.get('errorMessage'): errors.append(m['errorMessage'])
                    u = m.get('usage')
                    if u:
                        raw_usage.append(u)
                        for dest, src in [('input_tokens','input'),('output_tokens','output'),('cache_read_tokens','cacheRead'),('cache_write_tokens','cacheWrite'),('total_tokens','totalTokens')]: usage[dest] += u.get(src, 0) or 0
    for sess in (private/'sessions').glob('*.jsonl'):
        for line in sess.open(errors='replace'):
            try: e = json.loads(line)
            except ValueError: continue
            if e.get('type') == 'thinking_level_change': effective = e.get('thinkingLevel')
    return {'usage': {**usage, 'raw_provider_usage': raw_usage} if raw_usage else None, 'errors': errors,
            'thinking_effective': effective, 'tool_calls': tool_calls, 'model_response_count': messages}

def has_source(d, work):
    if d['track'] == 'frontend':
        p = work/'artifact.html'
        return p.exists() and p.stat().st_size > 100
    for p in (work/'src').rglob('*'):
        if not p.is_file(): continue
        baseline = PACKS['video']/'starter/remotion'/p.relative_to(work)
        if not baseline.exists() or sha256(p) != sha256(baseline): return True
    return False

def surviving_pid(private):
    """Discover a pi left alive by a hard runner crash, including legacy attempts."""
    needle = str(private/'sessions')
    def owns_stream(pid):
        try:
            result = subprocess.run(['lsof','-a','-p',str(pid),'-d','1','-Fn'],capture_output=True,text=True,timeout=5)
            return result.returncode == 0 and any(
                Path(line[1:]).parent == private and Path(line[1:]).match('attempt-*.jsonl')
                for line in result.stdout.splitlines() if line.startswith('n'))
        except (OSError, subprocess.TimeoutExpired):
            return False
    cached = PID_BY_SESSION.get(needle)
    if cached and owns_stream(cached):
        return cached
    PID_BY_SESSION.pop(needle,None)
    listing = subprocess.check_output(['ps','-axo','pid=,command='],text=True)
    title_only = []
    for line in listing.splitlines():
        try:
            pid, command = line.strip().split(None,1)
            args = shlex.split(command)
            i = args.index('--session-dir') if '--session-dir' in args else -1
            if i >= 0 and i+1 < len(args) and args[i+1] == needle and '--mode' in args and args[args.index('--mode')+1] == 'json':
                return int(pid)
            if len(args) == 1 and Path(args[0]).name == 'pi':
                title_only.append(int(pid))
        except (ValueError, IndexError): pass
    # Pi sets process.title to "pi", removing its original arguments from ps.
    # Its inherited stdout still identifies the exact independent attempt.
    for pid in title_only:
        if owns_stream(pid):
            PID_BY_SESSION[needle] = pid
            return pid
    return None

def finalize_evidence(meta, work, private):
    parsed = parse_events(private)
    atomic_json(meta.parent/'execution.json', {k:v for k,v in parsed.items() if k!='errors'})
    source_hashes = {str(p.relative_to(work)): sha256(p) for p in work.rglob('*')
                     if p.is_file() and p.suffix in {'.html','.tsx','.ts','.css','.js','.json','.md'}
                     and not any(part in {'node_modules','out','capture'} for part in p.relative_to(work).parts)}
    atomic_json(meta.parent/'source-hashes.json', source_hashes)
    return {'usage':parsed['usage'],'thinking_effective':parsed['thinking_effective'],
            'model_response_count':parsed['model_response_count'],'tool_call_count':len(parsed['tool_calls']),
            'execution_path':public_path(meta.parent/'execution.json'),
            'source_hashes_path':public_path(meta.parent/'source-hashes.json')}

def generate(meta):
    d = json.loads(meta.read_text())
    if d['status'] in {'succeeded', 'render_failed', 'generation_failed'}: return
    try:
        work, private, entry, request = prepare(meta)
        if d['status'] in {'awaiting_render','rendering'}:
            RENDER_QUEUE.put(meta); return
        update(meta, status='generating', phase='model_generation', started_at=d.get('started_at') or now(), error=None,
               request_path=public_path(meta.parent/'request.json'))
        attempts = d.get('attempts', [])
        # Do not start a second pi on the same files after an unclean shutdown.
        orphan = surviving_pid(private)
        handoff = d.get('pending_handoff')
        if orphan or handoff:
            update(meta, active_pid=orphan, phase='recovering_existing_process')
            original_start = datetime.fromisoformat(attempts[-1]['started_at']) if attempts else datetime.now().astimezone()
            orphan_budget = max(0, CONFIG['generation_timeout_seconds'] - sum(a.get('duration_ms',0) for a in attempts[:-1])/1000)
            recovered_code = None
            while orphan and surviving_pid(private):
                if STOP.wait(2): return
                if datetime.now().astimezone().timestamp()-original_start.timestamp() > orphan_budget:
                    try: os.killpg(orphan,signal.SIGTERM)
                    except ProcessLookupError: pass
                    time.sleep(3)
                    if surviving_pid(private):
                        try: os.killpg(orphan,signal.SIGKILL)
                        except ProcessLookupError: pass
                    recovered_code = -124
                    break
            if attempts and 'duration_ms' not in attempts[-1]:
                attempts[-1].update({'finished_at':now(),'duration_ms':round((datetime.now().astimezone().timestamp()-original_start.timestamp())*1000),
                                    'exit_code':recovered_code,'process_adoption':('thinking_policy_change' if handoff.get('reason')=='user_requested_thinking_change' else 'concurrency_change') if handoff else 'runner_recovery',
                                    'exit_code_observation':'generation budget timeout' if recovered_code == -124 else 'Unavailable after supervisor handoff; Pi process was not restarted'})
            parsed=parse_events(private)
            warning = 'Agent exceeded 45-minute wall-clock budget' if recovered_code == -124 else (parsed['errors'][-1] if parsed['errors'] else 'Pi continued through supervisor handoff; original process exit code unavailable')
            evidence=finalize_evidence(meta,work,private)
            fields = {'attempts':attempts,'active_pid':None,'pending_handoff':None,
                      'duration_ms':sum(a.get('duration_ms',0) for a in attempts),'generation_exit_code':recovered_code,
                      'generation_warning':warning,**evidence}
            if has_source(d,work):
                update(meta,status='awaiting_render',phase='awaiting_render',**fields)
                RENDER_QUEUE.put(meta);return
            update(meta,status='generation_failed',phase='generation_failed',finished_at=now(),
                   error=(parsed['errors'][-1] if parsed['errors'] else 'Agent did not produce the required source artifact')[:1600],**fields)
            return
        for old in attempts:
            if 'duration_ms' not in old and old.get('started_at'):
                old['duration_ms']=max(0,round((datetime.now().astimezone().timestamp()-datetime.fromisoformat(old['started_at']).timestamp())*1000))
                old['duration_observation']='conservative wall-time through recovery; original child exit time unavailable'
        used_seconds=sum(a.get('duration_ms',0) for a in attempts)/1000
        remaining=max(0,CONFIG['generation_timeout_seconds']-used_seconds)
        if remaining <= 0:
            if has_source(d,work):
                evidence=finalize_evidence(meta,work,private)
                update(meta,status='awaiting_render',phase='awaiting_render',attempts=attempts,generation_warning='Generation budget exhausted; preserved source captured as-is',**evidence)
                RENDER_QUEUE.put(meta)
            else:update(meta,status='generation_failed',phase='generation_failed',attempts=attempts,error='Total 45-minute generation budget exhausted',finished_at=now())
            return
        # A resumed run retains its session and files; never overwrite a completed original.
        attempt = len(attempts) + 1
        cmd = ['pi', '--provider', d['provider'], '--model', d['model'], '--thinking', request.get('thinking', d.get('thinking_requested', 'max')), '--mode', 'json', '--print',
               '--offline', '--no-extensions', '--no-skills', '--no-prompt-templates', '--no-context-files', '--no-themes',
               '--tools', 'read,bash,edit,write', '--session-dir', str(private/'sessions'),
               '--append-system-prompt', str(private/'policy.txt')]
        if attempt > 1 and list((private/'sessions').glob('*.jsonl')):
            cmd += ['--continue', '继续当前任务，从已保存文件和会话恢复，完成缺失交付，保留已有实现。']
        else: cmd += ['@'+entry, request['initial_message']]
        start = now(); attempts.append({'number': attempt, 'started_at': start, 'command': cmd, 'reason': 'initial' if attempt==1 else 'resume_after_interruption'})
        update(meta, attempts=attempts)
        def record_pid(pid):
            attempts[-1]['pid']=pid;attempts[-1]['pgid']=pid
            update(meta,attempts=attempts,active_pid=pid)
        code, duration = run_command(cmd, work, private/f'attempt-{attempt}.jsonl', private/f'attempt-{attempt}.stderr', remaining, record_pid)
        attempts[-1].update({'finished_at': now(), 'exit_code': code, 'duration_ms': duration})
        parsed = parse_events(private)
        atomic_json(meta.parent/'execution.json', {k:v for k,v in parsed.items() if k!='errors'})
        fields = {'attempts': attempts, 'duration_ms': sum(a.get('duration_ms',0) for a in attempts),
                  'usage': parsed['usage'], 'thinking_effective': parsed['thinking_effective'],
                  'model_response_count': parsed['model_response_count'], 'tool_call_count': len(parsed['tool_calls']),
                  'execution_path': public_path(meta.parent/'execution.json'), 'generation_exit_code': code,'active_pid':None}
        if STOP.is_set():
            update(meta, status='interrupted', phase='interrupted', **fields); return
        if not has_source(d, work):
            err = parsed['errors'][-1] if parsed['errors'] else ('Agent exceeded 45-minute wall-clock budget' if code==-124 else 'Agent did not produce the required source artifact')
            update(meta, status='generation_failed', phase='generation_failed', error=err[:1600], finished_at=now(), **fields)
        else:
            fields.update(finalize_evidence(meta,work,private))
            warning = parsed['errors'][-1] if parsed['errors'] else ('Agent exceeded 45-minute wall-clock budget' if code == -124 else f'Agent exited with code {code}' if code else None)
            update(meta, status='awaiting_render', phase='awaiting_render', generation_warning=warning, **fields)
            RENDER_QUEUE.put(meta)
    except Exception as e:
        update(meta, status='generation_failed', phase='harness_error', error=str(e)[:1600], finished_at=now())

def renderer():
    while True:
        meta = RENDER_QUEUE.get()
        try:
            if meta is None: return
            d = json.loads(meta.read_text()); work = meta.parent/'work'; private = meta.parent/'private'
            while not (ROOT/'bench/render.py').exists():
                if STOP.wait(5): return
            if STOP.is_set(): return
            update(meta, status='rendering', phase='media_capture')
            cmd = ['python3', str(ROOT/'bench/render.py'), str(work), '--track', d['track'], '--case-id', d['case_id']]
            code, duration = run_command(cmd, ROOT, private/'capture.stdout', private/'capture.stderr', CONFIG['render_timeout_seconds'])
            if STOP.is_set():
                update(meta, status='awaiting_render', phase='awaiting_render'); return
            result = None
            for line in reversed((private/'capture.stdout').read_text(errors='replace').splitlines()):
                try: result = json.loads(line); break
                except ValueError: continue
            if not isinstance(result, dict):
                result = {'status':'render_failed','error':(private/'capture.stderr').read_text(errors='replace')[-1400:] or f'Render exited {code}'}
            fields = {k: v for k,v in result.items() if not k.endswith('_path')}
            for key,value in result.items():
                if key.endswith('_path'):
                    p = work/value if value else None
                    fields[key] = public_path(p) if p and p.exists() and p.resolve().is_relative_to(work.resolve()) else None
            for key, filename in [('artifact_path','artifact.html'),('plan_path','plan.json' if d['track']=='frontend' else 'design-plan.md')]:
                if (work/filename).is_file(): fields[key] = public_path(work/filename)
            fields.update({'finished_at':now(), 'render_duration_ms':duration, 'phase':'complete' if result.get('status')=='succeeded' else result.get('status','render_failed')})
            fields.setdefault('status', 'render_failed')
            update(meta, **fields)
        except Exception as e:
            if meta: update(meta, status='render_failed', phase='harness_error', error=str(e), finished_at=now())
        finally: RENDER_QUEUE.task_done()

def model_worker(model_id, shard, workers):
    candidates = list((ROOT/'runs').glob(f'*/{model_id}/*/run-*/run.json'))
    # Cover both tracks and every subject before the second repetition.
    candidates.sort(key=lambda p: (json.loads(p.read_text())['run_number'], int(p.parent.parent.name[:2]), 0 if '/frontend/' in str(p) else 1))
    for meta in candidates[shard::workers]:
        if STOP.is_set(): break
        generate(meta)

def heartbeat():
    while not STOP.wait(15):
        with STATE_LOCK:
            publish()
            index = json.loads((ROOT/'results/index.json').read_text())
            counts = {}
            for r in index['runs']: counts[r['status']] = counts.get(r['status'],0)+1
            atomic_json(ROOT/'.runtime/runner-health.json', {'pid':os.getpid(), 'heartbeat_at':now(), 'counts':counts, 'render_queue':RENDER_QUEUE.qsize(),
                        'workers_per_model':CONFIG['workers_per_model'],'generation_capacity':len(CONFIG['models'])*CONFIG['workers_per_model']})
            print(json.dumps({'time':now(), 'counts':counts},ensure_ascii=False),flush=True)

def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--init-only',action='store_true'); a=parser.parse_args()
    init()
    if a.init_only: return
    lock = (ROOT/'.runtime/runner.lock').open('w')
    try: fcntl.flock(lock, fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError: raise SystemExit('A runner is already active')
    lock.write(str(os.getpid())); lock.flush()
    atomic_json(ROOT/'data/environment.json', {'python':platform.python_version(),'node':subprocess.check_output(['node','--version'],text=True).strip(),'os':platform.platform(),'machine':platform.machine(),'pi':subprocess.check_output(['pi','--version'],text=True).strip(),'recorded_at':now()})
    signal.signal(signal.SIGTERM, lambda *_: STOP.set()); signal.signal(signal.SIGINT, lambda *_: STOP.set())
    monitor=threading.Thread(target=heartbeat,daemon=True); monitor.start()
    renders=[threading.Thread(target=renderer,daemon=True) for _ in range(CONFIG['render_workers'])]
    for t in renders: t.start()
    workers=CONFIG['workers_per_model']
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(CONFIG['models'])*workers) as pool:
        futures=[pool.submit(model_worker,m['id'],i,workers) for m in CONFIG['models'] for i in range(workers)]
        for f in futures: f.result()
    if not STOP.is_set(): RENDER_QUEUE.join()
    for _ in renders: RENDER_QUEUE.put(None)
    for t in renders: t.join(timeout=5)
    STOP.set(); publish()
    print('Runner stopped; all states saved.',flush=True)

if __name__=='__main__': main()
