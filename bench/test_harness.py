#!/usr/bin/env python3
"""Read-only run integration audit and isolated recovery/file-server tests.

Fixtures live under .runtime and an ephemeral HTTP server uses a temporary
ROOT. No benchmark source, run metadata, queue, or running service is changed.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bench'))
import runner


def load_module(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'bench' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


server_module = load_module('visualbench_test_server', 'server.py')
render_module = load_module('visualbench_test_render', 'render.py')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def http_get(base, path, headers=None):
    try:
        with urlopen(Request(base + path, headers=headers or {}), timeout=20) as response:
            return response.status, dict(response.headers), response.read()
    except HTTPError as error:
        return error.code, dict(error.headers), error.read()


class RunnerRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='harness-runner-', dir=ROOT / '.runtime')
        self.root = Path(self.temp.name)
        self.private = self.root / 'private'
        self.private.mkdir()
        self.work = self.root / 'work'
        self.work.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_legacy_pi_pid_without_recorded_pid_is_discovered(self):
        listing = '\n'.join([
            '32001 /usr/bin/unrelated --mode json --session-dir /different/sessions',
            f'32002 node /opt/pi/dist/cli.js --provider test --mode json --session-dir {self.private / "sessions"} --print @INPUT.zh.txt',
        ])
        with patch.object(runner.subprocess, 'check_output', return_value=listing):
            self.assertEqual(runner.surviving_pid(self.private), 32002)

    def test_pid_match_requires_exact_session_directory(self):
        listing = f'32003 node /opt/pi/dist/cli.js --mode json --session-dir {self.private / "sessions-other"} --print task'
        with patch.object(runner.subprocess, 'check_output', return_value=listing):
            self.assertIsNone(runner.surviving_pid(self.private))

    def test_pi_process_title_is_matched_by_its_exact_attempt_stream(self):
        from types import SimpleNamespace
        result=SimpleNamespace(returncode=0,stdout=f'p32002\nf1\nn{self.private}/attempt-1.jsonl\n')
        with patch.object(runner.subprocess,'check_output',return_value='32002 pi'), \
             patch.object(runner.subprocess,'run',return_value=result), \
             patch.object(runner,'PID_BY_SESSION',{}):
            self.assertEqual(runner.surviving_pid(self.private),32002)

    def test_pi_process_title_does_not_match_neighboring_run(self):
        from types import SimpleNamespace
        result=SimpleNamespace(returncode=0,stdout=f'p32002\nf1\nn{self.private}-other/attempt-1.jsonl\n')
        with patch.object(runner.subprocess,'check_output',return_value='32002 pi'), \
             patch.object(runner.subprocess,'run',return_value=result), \
             patch.object(runner,'PID_BY_SESSION',{}):
            self.assertIsNone(runner.surviving_pid(self.private))

    def test_unchanged_video_starter_is_not_model_output(self):
        shutil.copytree(runner.PACKS['video'] / 'starter/remotion/src', self.work / 'src')
        self.assertFalse(runner.has_source({'track': 'video'}, self.work))

    def test_video_index_change_is_detected_with_unchanged_root(self):
        shutil.copytree(runner.PACKS['video'] / 'starter/remotion/src', self.work / 'src')
        path = self.work / 'src/index.tsx'
        path.write_text(path.read_text() + '\n// Independent model entrypoint implementation\n')
        self.assertTrue(runner.has_source({'track': 'video'}, self.work))

    def test_nested_video_component_is_detected_with_unchanged_root(self):
        shutil.copytree(runner.PACKS['video'] / 'starter/remotion/src', self.work / 'src')
        component = self.work / 'src/scenes/Scene.tsx'
        component.parent.mkdir()
        component.write_text('export const Scene = () => <div>Fixture model scene</div>;\n')
        self.assertTrue(runner.has_source({'track': 'video'}, self.work))

    def test_recovery_waits_for_existing_process_without_second_generation(self):
        import queue
        meta = self.root / 'run.json'
        html = self.work / 'artifact.html'
        html.write_text('<!doctype html><html><body>' + 'Fixture implementation. ' * 10 + '</body></html>')
        original_hash = digest(html)
        state = {'track': 'frontend', 'status': 'generating', 'started_at': runner.now(),
                 'attempts': [{'number': 1, 'started_at': runner.now()}]}
        meta.write_text(json.dumps(state))

        def isolated_update(path, **changes):
            data = json.loads(path.read_text())
            data.update(changes)
            path.write_text(json.dumps(data))
            return data

        parsed = {'usage': None, 'thinking_effective': 'max', 'errors': [], 'tool_calls': [], 'model_response_count': 0}
        queue_instance = queue.Queue()
        with patch.object(runner, 'prepare', return_value=(self.work, self.private, 'INPUT.zh.txt', {})), \
             patch.object(runner, 'update', side_effect=isolated_update), \
             patch.object(runner, 'surviving_pid', side_effect=[32002, None]), \
             patch.object(runner, 'parse_events', return_value=parsed), \
             patch.object(runner, 'RENDER_QUEUE', queue_instance), \
             patch.object(runner, 'STOP', threading.Event()), \
             patch.object(runner, 'run_command') as generated:
            runner.generate(meta)
        actual = json.loads(meta.read_text())
        generated.assert_not_called()
        self.assertEqual(actual['status'], 'awaiting_render')
        self.assertEqual(len(actual['attempts']), 1)
        self.assertIsNone(actual['active_pid'])
        self.assertEqual(queue_instance.get_nowait(), meta)
        self.assertEqual(digest(html), original_hash)
        self.assertTrue((meta.parent / 'execution.json').is_file())
        hashes = json.loads((meta.parent / 'source-hashes.json').read_text())
        self.assertEqual(hashes['artifact.html'], original_hash)

    def test_handoff_does_not_restart_pi_even_if_it_finished_before_adoption(self):
        self._handoff_case(source=True, expired=False)

    def test_handoff_without_source_is_one_failure_without_an_extra_attempt(self):
        self._handoff_case(source=False, expired=False)

    def test_handoff_retains_original_timeout_budget(self):
        self._handoff_case(source=True, expired=True)

    def test_high_request_reaches_pi_without_an_extra_attempt(self):
        self._thinking_command_case('high', 'high')

    def test_frozen_max_request_wins_during_recovery(self):
        self._thinking_command_case('high', 'max')

    def _thinking_command_case(self, metadata_thinking, frozen_thinking):
        meta = self.root / 'run.json'
        meta.write_text(json.dumps({'track':'frontend','status':'queued','provider':'test',
            'model':'test','thinking_requested':metadata_thinking,'attempts':[]}))
        def isolated_update(path, **changes):
            data=json.loads(path.read_text());data.update(changes);path.write_text(json.dumps(data));return data
        parsed={'usage':None,'thinking_effective':frozen_thinking,'errors':[],
                'tool_calls':[],'model_response_count':0}
        with patch.object(runner,'prepare',return_value=(self.work,self.private,'INPUT.zh.txt',
                 {'thinking':frozen_thinking,'initial_message':'fixture task'})), \
             patch.object(runner,'update',side_effect=isolated_update), \
             patch.object(runner,'surviving_pid',return_value=None), \
             patch.object(runner,'parse_events',return_value=parsed), \
             patch.object(runner,'STOP',threading.Event()), \
             patch.object(runner,'run_command',return_value=(0,1000)) as generated:
            runner.generate(meta)
        generated.assert_called_once()
        command=generated.call_args.args[0]
        self.assertEqual(command[command.index('--thinking')+1],frozen_thinking)
        self.assertEqual(len(json.loads(meta.read_text())['attempts']),1)

    def test_prepare_keeps_original_request_when_defaults_change(self):
        meta = self.root / 'run.json'
        meta.write_text(json.dumps({'track':'frontend','provider':'test','model':'test',
                                   'thinking_requested':'high'}))
        (self.work/'INPUT.zh.txt').write_text('frozen task')
        _,_,_,request=runner.prepare(meta)
        self.assertEqual(request['thinking'],'high')
        original=(self.root/'request.json').read_bytes()
        state=json.loads(meta.read_text());state['thinking_requested']='max'
        meta.write_text(json.dumps(state))
        _,_,_,resumed=runner.prepare(meta)
        self.assertEqual(resumed['thinking'],'high')
        self.assertEqual((self.root/'request.json').read_bytes(),original)

    def _handoff_case(self, source, expired):
        import queue
        from datetime import datetime, timedelta, timezone
        from unittest.mock import Mock
        meta = self.root / 'run.json'
        if source:
            (self.work / 'artifact.html').write_text('<html>' + 'fixture source ' * 20 + '</html>')
        start = (datetime.now(timezone.utc) - timedelta(seconds=2701 if expired else 10)).isoformat()
        meta.write_text(json.dumps({'track':'frontend','status':'generating','started_at':start,
            'attempts':[{'number':1,'started_at':start}], 'pending_handoff':{'reason':'concurrency_change'}}))
        def isolated_update(path, **changes):
            data=json.loads(path.read_text());data.update(changes);path.write_text(json.dumps(data));return data
        parsed={'usage':None,'thinking_effective':'max','errors':[],'tool_calls':[],'model_response_count':0}
        pending=queue.Queue()
        with patch.object(runner,'prepare',return_value=(self.work,self.private,'INPUT.zh.txt',{})), \
             patch.object(runner,'update',side_effect=isolated_update), \
             patch.object(runner,'surviving_pid',side_effect=[32002,32002,None] if expired else [None]), \
             patch.object(runner,'parse_events',return_value=parsed), \
             patch.object(runner,'RENDER_QUEUE',pending), \
             patch.object(runner,'STOP',Mock(wait=Mock(return_value=False))), \
             patch.object(runner.time,'sleep'), patch.object(runner.os,'killpg') as killed, \
             patch.object(runner,'run_command') as generated:
            runner.generate(meta)
        state=json.loads(meta.read_text())
        generated.assert_not_called()
        self.assertEqual(len(state['attempts']),1)
        self.assertIsNone(state['pending_handoff'])
        self.assertEqual(state['generation_exit_code'],-124 if expired else None)
        self.assertEqual(state['status'],'awaiting_render' if source else 'generation_failed')
        self.assertEqual(pending.qsize(),1 if source else 0)
        self.assertEqual(state['attempts'][0]['process_adoption'],'concurrency_change')
        self.assertEqual(killed.call_count,1 if expired else 0)


class GenerationOutcomeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='harness-generation-state-', dir=ROOT / '.runtime')
        self.root = Path(self.temp.name)
        self.work = self.root / 'work'
        (self.work / 'capture').mkdir(parents=True)
        (self.work / 'artifact.html').write_text('<html>Read-only model fixture source</html>')
        (self.work / 'plan.json').write_text('{"fixture":true}')
        (self.work / 'capture/poster.png').write_bytes(b'unchanged media fixture')
        (self.work / 'capture/preview.mp4').write_bytes(b'unchanged video fixture')

    def tearDown(self):
        self.temp.cleanup()

    def capture(self, exit_code, render_error=None, metadata_exists=True):
        meta = self.root / 'run.json'
        if metadata_exists:
            meta.write_text(json.dumps({'generation_exit_code': exit_code}))
        else:
            meta.unlink(missing_ok=True)
        before = {str(path): digest(path) for path in [self.work / 'artifact.html', self.work / 'capture/poster.png',
                                                       self.work / 'capture/preview.mp4']}
        if meta.exists():
            before[str(meta)] = digest(meta)

        def captured(_work, _case, _base, result):
            result.update(screenshot_path='capture/poster.png', video_path='capture/preview.mp4',
                          technical_checks={'technical_pass': True, 'errors': []})
            if render_error:
                raise RuntimeError(render_error)

        stdout = io.StringIO()
        argv = ['render.py', str(self.work), '--track', 'frontend', '--case-id', '01-pelican-bicycle']
        with patch.object(sys, 'argv', argv), patch.object(render_module, 'frontend', side_effect=captured), \
             patch.object(render_module.signal, 'signal'), contextlib.redirect_stdout(stdout):
            code = render_module.main()
        result = json.loads(stdout.getvalue().splitlines()[-1])
        self.assertEqual(result, json.loads((self.work / 'render-result.json').read_text()))
        for path, fingerprint in before.items():
            self.assertEqual(digest(path), fingerprint)
        self.assertEqual(result['screenshot_path'], 'capture/poster.png')
        self.assertEqual(result['video_path'], 'capture/preview.mp4')
        return code, result

    def test_timeout_remains_generation_failed_after_successful_capture(self):
        code, result = self.capture(-124)
        self.assertEqual(code, 1)
        self.assertEqual(result['status'], 'generation_failed')
        self.assertEqual(result['generation_status'], 'failed')
        self.assertEqual(result['generation_exit_code'], -124)
        self.assertEqual(result['render_outcome'], 'completed')
        self.assertTrue(result['technical_checks']['technical_pass'])
        self.assertIn('timed out', result['error'])

    def test_nonzero_generation_exit_remains_failed_after_successful_capture(self):
        code, result = self.capture(2)
        self.assertEqual(code, 1)
        self.assertEqual(result['status'], 'generation_failed')
        self.assertEqual(result['generation_status'], 'failed')
        self.assertEqual(result['render_outcome'], 'completed')
        self.assertIn('code 2', result['error'])

    def test_zero_generation_exit_and_successful_capture_are_succeeded(self):
        code, result = self.capture(0)
        self.assertEqual(code, 0)
        self.assertEqual(result['status'], 'succeeded')
        self.assertEqual(result['generation_status'], 'succeeded')

    def test_unknown_generation_exit_does_not_imply_failure(self):
        for exists in (True, False):
            with self.subTest(metadata_exists=exists):
                code, result = self.capture(None, metadata_exists=exists)
                self.assertEqual(code, 0)
                self.assertEqual(result['status'], 'succeeded')
                self.assertEqual(result['generation_status'], 'unknown')

    def test_generation_and_render_failures_both_remain_recorded(self):
        code, result = self.capture(-124, render_error='Fixture renderer could not load the page')
        self.assertEqual(code, 1)
        self.assertEqual(result['status'], 'generation_failed')
        self.assertEqual(result['render_outcome'], 'failed')
        self.assertEqual(result['render_error'], 'Fixture renderer could not load the page')
        self.assertIn('timed out', result['error'])
        self.assertFalse(result['technical_checks']['technical_pass'])

    def test_unknown_generation_exit_preserves_render_failure(self):
        code, result = self.capture(None, render_error='Fixture capture failure')
        self.assertEqual(code, 1)
        self.assertEqual(result['status'], 'render_failed')
        self.assertEqual(result['generation_status'], 'unknown')
        self.assertEqual(result['render_outcome'], 'failed')


class FileServerBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='harness-server-', dir=ROOT / '.runtime')
        self.root = Path(self.temp.name)
        self.run = self.root / 'runs/frontend/model-a/case-a/run-1'
        self.other_run = self.root / 'runs/frontend/model-b/case-b/run-1'
        self.work = self.run / 'work'
        for directory in (self.work, self.run / 'private', self.run / 'trajectory', self.other_run / 'work'):
            directory.mkdir(parents=True)
        (self.work / 'artifact.html').write_text('<html><body>Public fixture</body></html>')
        (self.work / 'other.html').write_text('<html><body>Secondary fixture</body></html>')
        (self.run / 'private/session.jsonl').write_text('private fixture')
        (self.work / 'raw.jsonl').write_text('non-exported fixture')
        (self.work / 'render.log').write_text('internal renderer fixture')
        (self.run / 'trajectory/session-1.jsonl').write_text('{"type":"session","fixture":true}\n')
        (self.run / 'trajectory/session-1.html').write_text('<html>Exported fixture</html>')
        (self.other_run / 'work/artifact.html').write_text('<html>Different run</html>')
        (self.work / 'private-alias.txt').symlink_to(self.run / 'private/session.jsonl')
        (self.work / 'other-run.txt').symlink_to(self.other_run / 'work/artifact.html')
        (self.work / 'log-alias.txt').symlink_to(self.work / 'render.log')
        (self.work / 'raw-alias.txt').symlink_to(self.work / 'raw.jsonl')
        (self.run.parent / 'run-2').symlink_to(self.other_run, target_is_directory=True)
        (self.work / 'outside-root.txt').symlink_to(ROOT / 'bench/config.json')
        self.patch_root = patch.object(server_module, 'ROOT', self.root)
        self.patch_root.start()

        class QuietHandler(server_module.Handler):
            def log_message(self, *_):
                pass

        self.httpd = ThreadingHTTPServer(('127.0.0.1', 0), QuietHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.base = f'http://127.0.0.1:{self.httpd.server_port}'
        self.prefix = '/results/runs/frontend/model-a/case-a/run-1'

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=2)
        self.patch_root.stop()
        self.temp.cleanup()

    def status(self, suffix):
        return http_get(self.base, self.prefix + suffix)[0]

    def test_artifact_and_secondary_html_get_csp(self):
        for name in ('artifact.html', 'other.html'):
            code, headers, data = http_get(self.base, self.prefix + '/work/' + name)
            self.assertEqual(code, 200)
            self.assertIn("frame-src 'none'", headers.get('Content-Security-Policy', ''))
        code, headers, data = http_get(self.base, self.prefix + '/work/artifact.html', {'Range': 'bytes=0-9'})
        self.assertEqual(code, 206)
        self.assertEqual(len(data), 10)

    def test_private_direct_and_symlink_are_blocked(self):
        for suffix in ('/private/session.jsonl', '/work/private-alias.txt'):
            self.assertEqual(self.status(suffix), 403)

    def test_cross_run_and_outside_root_symlinks_are_blocked(self):
        self.assertIn(self.status('/work/other-run.txt'), (403, 404))
        self.assertEqual(self.status('/work/outside-root.txt'), 403)

    def test_cross_run_directory_alias_is_blocked(self):
        path = '/results/runs/frontend/model-a/case-a/run-2/work/artifact.html'
        self.assertIn(http_get(self.base, path)[0], (403, 404))

    def test_private_extensions_cannot_be_renamed_via_symlink(self):
        for suffix in ('/work/render.log', '/work/raw.jsonl', '/work/log-alias.txt', '/work/raw-alias.txt'):
            with self.subTest(suffix=suffix):
                self.assertIn(self.status(suffix), (403, 404))

    def test_trajectory_exports_are_downloadable(self):
        code, headers, body = http_get(self.base, self.prefix + '/trajectory/session-1.jsonl')
        self.assertEqual(code, 200)
        self.assertIn('attachment', headers.get('Content-Disposition', ''))
        self.assertEqual(json.loads(body)['type'], 'session')
        self.assertEqual(self.status('/trajectory/session-1.html'), 200)

    def test_encoded_parent_traversal_is_blocked(self):
        self.assertEqual(self.status('/work/%2e%2e/private/session.jsonl'), 403)


def integration_audit(base):
    trajectories = json.loads((ROOT / 'data/trajectories.json').read_text()).get('runs', {})
    results = []
    for meta in sorted((ROOT / 'runs').glob('frontend/*/*/run-*/run.json')):
        data = json.loads(meta.read_text())
        if data['status'] != 'succeeded':
            continue
        report = {'run_id': data['id'], 'checks': {}, 'errors': []}
        checks = report['checks']
        for key in ('screenshot_path', 'video_path', 'artifact_path', 'code_path', 'plan_path', 'metadata_path', 'source_hashes_path'):
            if not data.get(key):
                report['errors'].append(f'Missing {key}')
                continue
            code, headers, body = http_get(base, data[key])
            checks[key] = {'http_status': code, 'bytes': len(body)}
            if code != 200:
                report['errors'].append(f'{key}: HTTP {code}')
            if key == 'screenshot_path' and code == 200:
                dimensions = struct.unpack('>II', body[16:24]) if body[:8] == b'\x89PNG\r\n\x1a\n' else None
                checks[key]['dimensions'] = dimensions
                if dimensions != (1280, 800):
                    report['errors'].append(f'Wrong screenshot dimensions: {dimensions}')
            if key == 'artifact_path' and code == 200:
                checks[key]['has_csp'] = 'Content-Security-Policy' in headers
        local_video = ROOT / data['video_path'].removeprefix('/results/')
        raw = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(local_video)], text=True))
        stream = next(s for s in raw['streams'] if s['codec_type'] == 'video')
        info = {'width': stream['width'], 'height': stream['height'], 'duration': float(raw['format']['duration']),
                'avg_frame_rate': stream['avg_frame_rate'], 'frame_count': stream.get('nb_frames')}
        checks['video_probe'] = info
        if (info['width'], info['height']) != (1280, 800) or abs(info['duration'] - 8) > .05:
            report['errors'].append('Captured video dimensions/duration mismatch')
        hashes = json.loads((meta.parent / 'source-hashes.json').read_text())
        mismatches = [name for name, expected in hashes.items() if not (meta.parent / 'work' / name).is_file()
                      or digest(meta.parent / 'work' / name) != expected]
        checks['source_hashes'] = {'checked_files': len(hashes), 'mismatches': mismatches}
        if mismatches:
            report['errors'].append('Raw model source hashes changed after generation: ' + ', '.join(mismatches))
        trace = trajectories.get(data['id'])
        if not trace:
            report['errors'].append('No exported trajectory in catalog')
        else:
            checks['trajectories'] = []
            for session in trace['sessions']:
                item = {'number': session['number']}
                for key in ('jsonl_path', 'html_path'):
                    if not session.get(key):
                        report['errors'].append('Missing trajectory ' + key)
                        continue
                    code, headers, body = http_get(base, session[key])
                    item[key] = {'http_status': code, 'bytes': len(body)}
                    if code != 200:
                        report['errors'].append(f'Trajectory {key}: HTTP {code}')
                    if key == 'jsonl_path' and code == 200:
                        actual_hash = hashlib.sha256(body).hexdigest()
                        item[key]['sha256_match'] = actual_hash == session['sha256']
                        if actual_hash != session['sha256']:
                            report['errors'].append('Downloaded trajectory hash mismatch')
                        native = sorted((meta.parent / 'private/sessions').glob('*.jsonl'))[session['number'] - 1]
                        item[key]['native_session_unchanged'] = digest(native) == actual_hash
                        if digest(native) != actual_hash:
                            report['errors'].append('Trajectory differs from native Pi session')
                checks['trajectories'].append(item)
        report['passed'] = not report['errors']
        results.append(report)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:4174')
    parser.add_argument('--unit-only', action='store_true')
    parser.add_argument('--integration-only', action='store_true')
    parser.add_argument('--report', type=Path, default=ROOT / '.runtime/harness-test-report.json')
    args = parser.parse_args()
    report = {'checked_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()), 'model_source_modified': False}
    if not args.integration_only:
        suite = unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(RunnerRecoveryTests),
                                   unittest.defaultTestLoader.loadTestsFromTestCase(GenerationOutcomeTests),
                                   unittest.defaultTestLoader.loadTestsFromTestCase(FileServerBoundaryTests)])
        results = unittest.TextTestRunner(verbosity=2).run(suite)
        report['harness_tests'] = {'run': results.testsRun, 'passed': results.wasSuccessful(),
                                   'failures': [{'test': str(test), 'traceback': trace} for test, trace in results.failures],
                                   'errors': [{'test': str(test), 'traceback': trace} for test, trace in results.errors]}
    if not args.unit_only:
        report['actual_runs'] = integration_audit(args.base_url)
    report['passed'] = report.get('harness_tests', {}).get('passed', True) and all(r['passed'] for r in report.get('actual_runs', []))
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'passed': report['passed'], 'harness_tests': report.get('harness_tests', {}).get('run', 0),
                      'actual_runs': len(report.get('actual_runs', [])), 'report': str(args.report)}))
    return 0 if report['passed'] else 1


if __name__ == '__main__':
    sys.exit(main())
