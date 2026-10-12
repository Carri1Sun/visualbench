#!/usr/bin/env python3
"""Collect unmodified model outputs for VisualBench, without aesthetic scoring.

Usage: python3 bench/render.py WORK --track frontend|video --case-id CASE_ID
The final stdout line is a JSON result, also saved as WORK/render-result.json.
All artifact paths in the result are relative to WORK. Frontend captures use
the single shared Ego TaskSpace under bench/browser.lock; video renders use a
separate global lock and at most two Remotion workers. No model source is edited.
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from urllib.parse import quote
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / 'bench'
ACTIVE_CHILD = None
DEADLINE = None


def remaining_timeout(requested: float):
    remaining = DEADLINE - time.monotonic() if DEADLINE is not None else requested
    if remaining <= 0:
        raise RuntimeError('Total capture/render time budget exhausted')
    return min(requested, remaining)


def terminate_child(process):
    """Terminate the complete child process group, including Chromium/ffmpeg."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass
    # Descendants can survive briefly after the group leader has exited.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def interrupt_render(signum, _frame):
    if ACTIVE_CHILD is not None:
        terminate_child(ACTIVE_CHILD)
    raise RuntimeError(f'Render interrupted by {signal.Signals(signum).name}; child process group terminated')


def write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


def relative(work: Path, path: Path | None):
    return str(path.relative_to(work)) if path and path.is_file() else None


def public_url(work: Path, path: str):
    """Array members are not rewritten by the parent runner's *_path mapping."""
    try:
        project_path = work.relative_to(ROOT)
    except ValueError:
        return path
    if project_path.parts and project_path.parts[0] == 'runs':
        return '/results/' + quote(str(project_path / path))
    return path


def apply_generation_outcome(work: Path, result: dict):
    """Media capture cannot turn a failed generation into a successful trial."""
    result['generation_status'] = 'unknown'
    try:
        metadata = json.loads((work.parent / 'run.json').read_text(encoding='utf-8'))
    except FileNotFoundError:
        return
    except (OSError, ValueError) as error:
        result['generation_metadata_warning'] = str(error)
        return
    if not isinstance(metadata, dict):
        result['generation_metadata_warning'] = 'Run metadata is not a JSON object'
        return
    exit_code = metadata.get('generation_exit_code')
    result['generation_exit_code'] = exit_code
    # Old processes can have an unknown exit code. Missing, null, or malformed
    # metadata does not provide evidence of generation failure.
    if not isinstance(exit_code, int) or isinstance(exit_code, bool):
        return
    if exit_code == 0:
        result['generation_status'] = 'succeeded'
        return
    result['generation_status'] = 'failed'
    result['status'] = 'generation_failed'
    generation_error = (f'Generation timed out (exit code {exit_code})' if abs(exit_code) == 124
                        else f'Generation exited with code {exit_code}')
    if result.get('error'):
        result['render_error'] = result['error']
        result['error'] = generation_error + '; media capture: ' + result['render_error']
    else:
        result['error'] = generation_error


@contextlib.contextmanager
def lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        while True:
            remaining_timeout(1)
            try:
                fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                time.sleep(.2)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def run_logged(args, cwd: Path, log: Path, timeout=1800, input_text=None):
    global ACTIVE_CHILD
    timeout = remaining_timeout(timeout)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open('w', encoding='utf-8') as output:
        output.write('$ ' + ' '.join(map(str, args)) + '\n')
        output.flush()
        # Each command has its own process group so timed-out renderers cannot
        # remain behind consuming resources or writing a partial result.
        process = subprocess.Popen(list(map(str, args)), cwd=cwd, stdin=subprocess.PIPE if input_text else subprocess.DEVNULL,
                                   stdout=output, stderr=subprocess.STDOUT, text=True, start_new_session=True)
        ACTIVE_CHILD = process
        try:
            process.communicate(input=input_text, timeout=timeout)
        except subprocess.TimeoutExpired:
            terminate_child(process)
            output.write(f'\nTIMEOUT after {timeout}s\n')
            return {'exit_code': 124, 'timeout': True, 'log': str(log)}
        finally:
            ACTIVE_CHILD = None
    return {'exit_code': process.returncode, 'timeout': False, 'log': str(log)}


def probe(path: Path):
    global ACTIVE_CHILD
    timeout = remaining_timeout(30)
    p = subprocess.Popen(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(path)],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, start_new_session=True)
    ACTIVE_CHILD = p
    try:
        stdout, stderr = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        terminate_child(p)
        return {'error': 'ffprobe timed out'}
    finally:
        ACTIVE_CHILD = None
    if p.returncode:
        return {'error': stderr.strip()[-2000:] or 'ffprobe failed'}
    raw = json.loads(stdout)
    video = next((s for s in raw.get('streams', []) if s.get('codec_type') == 'video'), None)
    if video is None:
        return {'error': 'No video stream'}
    ratio = video.get('avg_frame_rate', '0/1').split('/')
    fps = float(ratio[0]) / float(ratio[1]) if len(ratio) == 2 and float(ratio[1]) else 0
    return {'width': video.get('width'), 'height': video.get('height'), 'fps': fps,
            'duration': float(raw.get('format', {}).get('duration') or video.get('duration') or 0),
            'codec': video.get('codec_name'), 'pixel_format': video.get('pix_fmt'),
            'frame_count': int(video['nb_frames']) if str(video.get('nb_frames', '')).isdigit() else None,
            'audio': any(s.get('codec_type') == 'audio' for s in raw.get('streams', [])),
            'bytes': path.stat().st_size}


def media_errors(info, config, alpha=False):
    if info.get('error'):
        return [info['error']]
    errors = []
    if (info.get('width'), info.get('height')) != (config['width'], config['height']):
        errors.append('wrong dimensions')
    if abs(info.get('fps', 0) - config['fps']) > .01:
        errors.append('wrong fps')
    duration = config['duration_frames'] / config['fps']
    if abs(info.get('duration', 0) - duration) > max(.1, 2 / config['fps']):
        errors.append('wrong duration')
    if alpha and (info.get('codec') != 'prores' or not info.get('pixel_format', '').startswith('yuva')):
        errors.append('master lacks expected ProRes alpha format')
    return errors


def collect_source(work: Path, track: str):
    capture = work / 'capture'
    capture.mkdir(exist_ok=True)
    if track == 'frontend':
        files = [work / 'artifact.html']
        files += [p for p in sorted(work.rglob('*')) if p.is_file() and p.suffix in {'.css', '.js', '.tsx', '.jsx', '.ts'}
                  and not any(part in {'node_modules', 'vendor', 'assets', 'capture', '.git'} for part in p.relative_to(work).parts)]
    else:
        files = sorted((work / 'src').rglob('*')) if (work / 'src').is_dir() else []
        files += [work / name for name in ('package.json', 'case.config.json', 'remotion.config.ts', 'remotion.config.js', 'tsconfig.json')]
    files = [p for p in dict.fromkeys(files) if p.is_file() and p.stat().st_size < 2_000_000]
    if not files:
        return None
    output = capture / 'source.txt'
    with output.open('w', encoding='utf-8') as f:
        for source in files:
            f.write(f'\n{"=" * 72}\n{source.relative_to(work)}\n{"=" * 72}\n')
            f.write(source.read_text(encoding='utf-8', errors='replace'))
            f.write('\n')
    return output


def public_video_console(work: Path):
    """Publish renderer diagnostics separately from private agent sessions."""
    logs = []
    for name in ('typecheck.log', 'render.log', 'render-alpha.log', 'verify.log'):
        path = work / 'capture' / name
        if path.is_file():
            logs.append({'phase': name.removesuffix('.log'), 'text': path.read_text(errors='replace')[-100_000:]})
    if logs:
        path = work / 'capture/console.json'
        write_json(path, logs)
        return relative(work, path)
    return None


def frontend(work: Path, case_id: str, base_url: str, result: dict):
    artifact = work / 'artifact.html'
    if not artifact.is_file():
        raise RuntimeError('Model did not produce artifact.html')
    capture = work / 'capture'
    try:
        run_path = work.relative_to(ROOT)
    except ValueError:
        raise RuntimeError('Frontend work directory must be inside the project for the /results route')
    url = base_url.rstrip('/') + '/results/' + quote(str(run_path)) + '/artifact.html'
    # Fail clearly if the results server is unavailable or misconfigured.
    with urlopen(url, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError(f'Results server returned HTTP {response.status}')
    # Chromium resolves *.localhost to loopback. A distinct host separates
    # even domain cookies from the user's 127.0.0.1 gallery / live previews.
    capture_url = url.replace('http://127.0.0.1:4175/', 'http://capture.localhost:4175/', 1)
    cfg = {'url': capture_url, 'captureDir': str(capture), 'spacePath': str(BENCH / 'browser-space.json'),
           'mobile': int(case_id.split('-')[0]) >= 16}
    script = 'const benchConfig = ' + json.dumps(cfg) + ';\n' + (BENCH / 'capture_frontend.mjs').read_text()
    with lock(BENCH / 'browser.lock'):
        capture_result = run_logged(['ego-browser', 'nodejs'], work, capture / 'browser.log', timeout=180, input_text=script)
    result['console_path'] = relative(work, capture / 'console.json')
    result['screenshot_path'] = relative(work, capture / 'poster.png')
    result['mobile_screenshot_path'] = relative(work, capture / 'mobile.png')
    result['capture_log_path'] = relative(work, capture / 'browser.log')
    if capture_result['exit_code']:
        log = (capture / 'browser.log').read_text(errors='replace')[-3000:]
        if any(s in log.lower() for s in ('user control', 'user-owned', 'inactive', 'unassigned', 'not agent', 'ownership')):
            result['status'] = 'capture_blocked'
        raise RuntimeError('Ego capture failed: ' + log)
    metadata = json.loads((capture / 'capture.json').read_text())
    frames = metadata['frames']
    if not frames:
        raise RuntimeError('Ego screencast produced no frames')
    # Preserve the actual CDP frame timing. Static pages naturally send fewer
    # frames; holding those frames preserves the eight-second observation.
    first_time = frames[0]['timestamp']
    concat = []
    for i, frame in enumerate(frames):
        elapsed = max(0, frame['timestamp'] - first_time)
        if elapsed >= 8:
            break
        next_elapsed = frames[i + 1]['timestamp'] - first_time if i + 1 < len(frames) else 8
        duration = max(.001, min(8, next_elapsed) - elapsed)
        concat += [f"file 'frames/{frame['file']}'", f'duration {duration:.6f}']
    concat += [concat[-2]]
    (capture / 'frames.ffconcat').write_text('ffconcat version 1.0\n' + '\n'.join(concat) + '\n')
    encoded = run_logged(['ffmpeg', '-hide_banner', '-loglevel', 'warning', '-y', '-f', 'concat', '-safe', '0',
                          '-i', capture / 'frames.ffconcat', '-t', '8', '-vf', 'fps=30', '-c:v', 'libx264',
                          '-preset', 'fast', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', capture / 'preview.mp4'],
                         work, capture / 'encode.log', timeout=120)
    if encoded['exit_code']:
        raise RuntimeError('Screencast encoding failed; see capture/encode.log')
    info = probe(capture / 'preview.mp4')
    errors = media_errors(info, {'width': 1280, 'height': 800, 'fps': 30, 'duration_frames': 240})
    console = json.loads((capture / 'console.json').read_text())
    exceptions = [e for e in console if e['method'] == 'Runtime.exceptionThrown']
    console_errors = [e for e in console if e['method'] == 'Runtime.consoleAPICalled' and e.get('params', {}).get('type') == 'error']
    result.update(video_path=relative(work, capture / 'preview.mp4'), width=1280, height=800,
                  technical_checks={'technical_pass': not errors and not exceptions, 'errors': errors,
                                    'runtime_exception_count': len(exceptions), 'console_error_count': len(console_errors),
                                    'desktop': metadata['desktop'], 'mobile': metadata['mobile'],
                                    'poster_at_ms': metadata['poster_at_ms'], 'screencast_frame_count': len(frames),
                                    'video': info, 'interaction': metadata['interaction'], 'clock': metadata['clock']})
    result['technical_checks']['storage_isolation'] = metadata['storage_isolation']
    result['technical_checks']['interaction_actions'] = {
        'status': 'not_performed',
        'note': 'The supplied semantic interaction checklist has not been executed. This capture observes the initial state only.',
    }
    if errors:
        result['status'] = 'partial'
        result['error'] = '; '.join(errors)
    # Raw JPEG frames are transient capture buffers, not model artifacts. The
    # complete recording, timing ledger, screenshots, and console are retained.
    if not errors:
        shutil.rmtree(capture / 'frames')


def video(work: Path, case_id: str, result: dict):
    capture = work / 'capture'
    out = work / 'out'
    out.mkdir(exist_ok=True)
    manifest = json.loads((ROOT / 'video-bench-inputs-v1/manifest.json').read_text())
    canonical = next((c for c in manifest['cases'] if c['id'] == case_id), None)
    if not canonical:
        raise RuntimeError('Unknown video case: ' + case_id)
    config = {k: canonical[k] for k in ('width', 'height', 'fps', 'duration_frames', 'alpha_required')}
    result.update(width=config['width'], height=config['height'])
    cli = work / 'node_modules/.bin/remotion'
    if not cli.exists():
        cli = ROOT / '.runtime/remotion/node_modules/.bin/remotion'
    entry = work / 'src/index.tsx'
    browser_candidates = [p for base in (ROOT / '.remotion', ROOT / '.runtime/remotion/node_modules/.remotion')
                          for p in base.rglob('chrome-headless-shell') if p.is_file() and os.access(p, os.X_OK)]
    browser_args = ['--browser-executable=' + str(browser_candidates[0])] if browser_candidates else []
    logs = {}
    checks = {'technical_pass': False, 'errors': [], 'canonical_config': config, 'renders': {},
              'semantic_and_aesthetic_checks': 'not scored; inspect the media and source'}
    result['technical_checks'] = checks
    result['console_path'] = 'capture/console.json'
    video_path = out / 'video.mp4'
    alpha_path = out / 'overlay.mov'
    with lock(ROOT / '.runtime/remotion/render.lock'):
        tsc = work / 'node_modules/.bin/tsc'
        if tsc.exists() and (work / 'tsconfig.json').exists():
            typecheck = run_logged([tsc, '--noEmit'], work, capture / 'typecheck.log', timeout=120)
            checks['typecheck'] = {'exit_code': typecheck['exit_code'], 'log_path': 'capture/typecheck.log'}
        if not video_path.exists() or media_errors(probe(video_path), config):
            if video_path.exists():
                checks['original_video'] = {'path': 'out/video.mp4', **probe(video_path)}
                # Keep the model's original render, even if invalid.
                video_path = capture / 'rendered-video.mp4'
            if not cli.exists() or not entry.exists():
                raise RuntimeError('Remotion CLI or src/index.tsx is missing')
            if not browser_candidates:
                raise RuntimeError('Shared Remotion browser is missing; prepare it once before rendering')
            command = [cli, 'render', 'src/index.tsx', 'Main', video_path, '--codec=h264', '--concurrency=2', '--log=error'] + browser_args
            rendered = run_logged(command, work, capture / 'render.log', timeout=1800)
            logs['video'] = 'capture/render.log'
            checks['renders']['video'] = {'exit_code': rendered['exit_code'], 'reused': False}
            if rendered['exit_code']:
                if video_path.exists():
                    checks['partial_video'] = probe(video_path)
                raise RuntimeError('Remotion render failed; see capture/render.log')
        else:
            checks['renders']['video'] = {'exit_code': 0, 'reused': True}
            (capture / 'render.log').write_text('Reused model-produced out/video.mp4 after ffprobe validation.\n')
        checks['video'] = probe(video_path)
        checks['errors'] += media_errors(checks['video'], config)
        result['video_path'] = relative(work, video_path)
        if config['alpha_required']:
            if not alpha_path.exists() or media_errors(probe(alpha_path), config, alpha=True):
                if not browser_candidates:
                    raise RuntimeError('Shared Remotion browser is missing; cannot render transparent master')
                if alpha_path.exists():
                    checks['original_alpha'] = {'path': 'out/overlay.mov', **probe(alpha_path)}
                    alpha_path = capture / 'rendered-overlay.mov'
                rendered = run_logged([cli, 'render', 'src/index.tsx', 'Main', alpha_path, '--codec=prores',
                                       '--prores-profile=4444', '--pixel-format=yuva444p10le', '--image-format=png',
                                       '--concurrency=2', '--log=error'] + browser_args, work, capture / 'render-alpha.log', timeout=1800)
                logs['alpha'] = 'capture/render-alpha.log'
                checks['renders']['alpha'] = {'exit_code': rendered['exit_code'], 'reused': False}
                if rendered['exit_code']:
                    checks['errors'].append('Transparent Remotion render failed; see capture/render-alpha.log')
            else:
                checks['renders']['alpha'] = {'exit_code': 0, 'reused': True}
            if alpha_path.exists():
                checks['alpha'] = probe(alpha_path)
                checks['errors'] += media_errors(checks['alpha'], config, alpha=True)
                result['alpha_path'] = relative(work, alpha_path)
        # Capture six evenly spaced actual frames from the final preview and a
        # midpoint poster. Existing model stills remain untouched in out/.
        frame_dir = capture / 'keyframes'
        frame_dir.mkdir(exist_ok=True)
        frame_numbers = [round((config['duration_frames'] - 1) * i / 5) for i in range(6)]
        result['frame_paths'] = []
        keyframe_records = []
        for i, frame in enumerate(frame_numbers):
            target = frame_dir / f'{i + 1:02d}-frame-{frame:05d}.png'
            target.unlink(missing_ok=True)
            extracted = run_logged(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', video_path,
                                    '-vf', f'select=eq(n\\,{frame})', '-frames:v', '1', '-update', '1', target],
                                   work, capture / f'frame-{i + 1}.log', timeout=90)
            if extracted['exit_code'] or not target.exists():
                checks['errors'].append(f'Could not extract frame {frame}')
            else:
                result['frame_paths'].append(relative(work, target))
                keyframe_records.append({'frame': frame, 'seconds': frame / config['fps'],
                                         'path': public_url(work, relative(work, target))})
        poster = capture / 'poster.png'
        poster.unlink(missing_ok=True)
        midpoint = config['duration_frames'] // 2
        extracted = run_logged(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', video_path,
                                '-vf', f'select=eq(n\\,{midpoint})', '-frames:v', '1', '-update', '1', poster],
                               work, capture / 'poster.log', timeout=90)
        result['screenshot_path'] = relative(work, poster)
        if extracted['exit_code'] or not poster.exists():
            checks['errors'].append('Could not extract midpoint poster')
        # verify_outputs.py expects specific file names. An isolated symlink
        # view checks exactly the collected media without rewriting model files.
        with tempfile.TemporaryDirectory(prefix='visualbench-verify-') as temp:
            view = Path(temp)
            (view / 'out/frames').mkdir(parents=True)
            write_json(view / 'case.config.json', config)
            for name in ('design-plan.md', 'implementation.md'):
                if (work / name).is_file():
                    (view / name).symlink_to(work / name)
            for target, source in [('out/video.mp4', video_path), ('out/poster.png', poster), ('out/overlay.mov', alpha_path)]:
                if source.is_file():
                    (view / target).symlink_to(source)
            for image in frame_dir.glob('*.png'):
                (view / 'out/frames' / image.name).symlink_to(image)
            verify = run_logged([sys.executable, ROOT / 'video-bench-inputs-v1/scripts/verify_outputs.py', view],
                                work, capture / 'verify.log', timeout=60)
            verify_text = (capture / 'verify.log').read_text()
            try:
                checks['pack_verifier'] = json.loads(verify_text[verify_text.index('{'):])
                checks['errors'] += checks['pack_verifier'].get('errors', [])
            except (ValueError, json.JSONDecodeError):
                checks['errors'].append('Pack verification failed to produce JSON')
            checks['pack_verifier_exit_code'] = verify['exit_code']
    checks['errors'] = list(dict.fromkeys(checks['errors']))
    checks['technical_pass'] = not checks['errors']
    checks['keyframe_numbers'] = frame_numbers
    checks['poster_frame'] = midpoint
    result['render_log_paths'] = logs
    write_json(capture / 'keyframes.json', {
        'fps': config['fps'],
        'frames': keyframe_records,
    })
    result['keyframes_path'] = 'capture/keyframes.json'
    if checks['errors']:
        result['status'] = 'partial'
        result['error'] = '; '.join(checks['errors'])


def main():
    global DEADLINE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('work', type=Path)
    parser.add_argument('--track', choices=['frontend', 'video'], required=True)
    parser.add_argument('--case-id', required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:4175')
    parser.add_argument('--timeout-seconds', type=float, help='Total budget including locks, render, and capture; defaults to runner budget minus 30s')
    args = parser.parse_args()
    work = args.work.resolve()
    work.mkdir(parents=True, exist_ok=True)
    started = time.time()
    budget = args.timeout_seconds
    if budget is None:
        try:
            budget = max(1, float(json.loads((BENCH / 'config.json').read_text())['render_timeout_seconds']) - 30)
        except (OSError, KeyError, ValueError):
            budget = 1770
    DEADLINE = time.monotonic() + budget
    signal.signal(signal.SIGTERM, interrupt_render)
    signal.signal(signal.SIGINT, interrupt_render)
    result = {'status': 'completed', 'track': args.track, 'case_id': args.case_id, 'error': None,
              'screenshot_path': None, 'video_path': None, 'code_path': None, 'plan_path': None,
              'console_path': None, 'width': None, 'height': None, 'technical_checks': {}}
    try:
        result['code_path'] = relative(work, collect_source(work, args.track))
        plan_names = ['plan.json', 'design-plan.md'] if args.track == 'frontend' else ['design-plan.md', 'plan.json']
        result['plan_path'] = next((name for name in plan_names if (work / name).is_file()), None)
        if args.track == 'frontend':
            frontend(work, args.case_id, args.base_url, result)
        else:
            video(work, args.case_id, result)
    except Exception as error:
        if result['status'] != 'capture_blocked':
            result['status'] = 'failed'
        result['error'] = str(error)
        result['technical_checks']['technical_pass'] = False
    if args.track == 'video':
        result['console_path'] = public_video_console(work)
    result['render_outcome'] = result['status']
    if result['status'] == 'capture_blocked':
        result['requires_user_action'] = True
    result['status'] = 'succeeded' if result['status'] in {'completed', 'partial'} else 'render_failed'
    apply_generation_outcome(work, result)
    for key in ('frame_paths',):
        if key in result:
            result[key] = [public_url(work, path) for path in result[key]]
    result['elapsed_seconds'] = round(time.time() - started, 3)
    result['rendered_at'] = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    write_json(work / 'render-result.json', result)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result['status'] == 'succeeded' else 1


if __name__ == '__main__':
    sys.exit(main())
