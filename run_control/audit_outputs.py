#!/usr/bin/env python3
"""Audit saved run evidence without changing model files or runner metadata.

Writes data/audits.json. --watch refreshes it while the queue runs. Source
presence is an observation, not a semantic or aesthetic quality judgment.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import time

from common import ROOT, PACKS, atomic_json, now, sha256


ACTIVE_STATUSES = {'queued', 'running', 'generating', 'interrupted', 'awaiting_render', 'rendering'}
IMMUTABLE_FILES = {'case.config.json', 'package.json', 'package-lock.json', 'TASK.json', 'PROMPT.md'}


def immutable_input(name):
    path = Path(name)
    if path.is_absolute() or '..' in path.parts:
        return False
    return (name in IMMUTABLE_FILES
            or (len(path.parts) == 1 and name.startswith('INPUT.') and name.endswith('.txt'))
            or path.parts[:1] in {('assets',), ('vendor',), ('fonts',)}
            or path.parts[:2] in {('public', 'input'), ('public', 'fonts')})


def read_json(path):
    return json.loads(path.read_text())


def contained_file(work, name):
    path = work / name
    if Path(name).is_absolute() or '..' in Path(name).parts or not path.resolve().is_relative_to(work.resolve()):
        raise ValueError('Path escapes the run working directory')
    return path


def audit_inputs(work, request):
    expected = {name: digest for name, digest in request.get('input_files', {}).items() if immutable_input(name)}
    changes = []
    for name, digest in sorted(expected.items()):
        try:
            path = contained_file(work, name)
            actual = sha256(path) if path.is_file() else None
            if actual != digest:
                changes.append({'path': name, 'change': 'missing' if actual is None else 'modified',
                                'expected_sha256': digest, 'actual_sha256': actual})
        except (OSError, ValueError) as error:
            changes.append({'path': name, 'change': 'unreadable_or_outside_work',
                            'expected_sha256': digest, 'actual_sha256': None, 'error': str(error)})
    return {'checked_file_count': len(expected), 'all_match': not changes if expected else None,
            'changes': changes}


def source_presence(work, track, request):
    if track == 'frontend':
        source = contained_file(work, 'artifact.html')
        return {'artifact_present': source.is_file(),
                'artifact_bytes': source.stat().st_size if source.is_file() else None,
                'plan_present': (work/'plan.json').is_file(),
                'has_authored_source': source.is_file() and source.stat().st_size > 0}
    baseline = {name: digest for name, digest in request.get('input_files', {}).items() if name.startswith('src/')}
    if not baseline:
        starter = PACKS['video']/'starter/remotion'
        baseline = {str(p.relative_to(starter)): sha256(p) for p in (starter/'src').rglob('*') if p.is_file()}
    current = {}
    for path in sorted((work/'src').rglob('*')):
        if path.is_file():
            name = str(path.relative_to(work))
            current[name] = sha256(contained_file(work, name))
    added = sorted(set(current) - set(baseline))
    modified = sorted(name for name in current.keys() & baseline.keys() if current[name] != baseline[name])
    removed = sorted(set(baseline) - set(current))
    return {'source_file_count': len(current), 'source_sha256': current,
            'entry_present': (work/'src/index.tsx').is_file(),
            'root_present': 'src/Root.tsx' in current,
            'root_changed': 'src/Root.tsx' in current and current['src/Root.tsx'] != baseline.get('src/Root.tsx'),
            'added_files': added, 'modified_files': modified, 'removed_files': removed,
            'plan_present': (work/'design-plan.md').is_file(),
            'implementation_notes_present': (work/'implementation.md').is_file(),
            'has_authored_source': bool(added or modified)}


def dependency_versions(work, track, cache):
    """Check declared and installed versions; this does not attest package bytes."""
    if track == 'frontend':
        expected = read_json(PACKS['frontend']/'vendor/three/version.json')['version']
        path = contained_file(work, 'vendor/three/version.json')
        actual = read_json(path).get('version') if path.is_file() else None
        return {'kind': 'bundled_three', 'versions': {'three': {'expected': expected, 'actual': actual}},
                'versions_match': actual == expected, 'package_bytes_verified_by': 'immutable_input_changes'}
    canonical = read_json(PACKS['video']/'starter/remotion/package.json')
    expected = {**canonical.get('dependencies', {}), **canonical.get('devDependencies', {})}
    manifest = read_json(contained_file(work, 'package.json')) if (work/'package.json').is_file() else {}
    declared = {**manifest.get('dependencies', {}), **manifest.get('devDependencies', {})}
    versions = {}
    for name, version in sorted(expected.items()):
        package = work/'node_modules'/name/'package.json'
        actual = None
        error = None
        try:
            resolved = package.resolve()
            if not resolved.is_relative_to(ROOT.resolve()):
                raise ValueError('Dependency package resolves outside the benchmark project')
            if resolved.is_file():
                stat = resolved.stat()
                key = (str(resolved), stat.st_mtime_ns, stat.st_size)
                if key not in cache:
                    cache[key] = read_json(resolved).get('version')
                actual = cache[key]
        except (OSError, ValueError) as exc:
            error = str(exc)
        versions[name] = {'expected': version, 'declared': declared.get(name), 'installed': actual,
                          'matches': actual == version and declared.get(name) == version}
        if error:
            versions[name]['error'] = error
    unexpected = sorted(set(declared) - set(expected))
    return {'kind': 'remotion_installed_dependencies', 'versions': versions,
            'unexpected_declared_packages': unexpected,
            'versions_match': all(v['matches'] for v in versions.values()) and not unexpected,
            'scope': 'Exact declared and installed package versions; package contents are not byte-verified.'}


def usage_observations(meta, run):
    execution_path = meta.parent/'execution.json'
    execution = read_json(execution_path) if execution_path.is_file() else {}
    usage = execution.get('usage') or run.get('usage') or {}
    raw = usage.get('raw_provider_usage') or []
    reasoning = []
    costs = []
    for item in raw:
        value = item.get('reasoning', item.get('reasoning_tokens'))
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            reasoning.append(value)
        cost = item.get('cost')
        value = cost.get('total') if isinstance(cost, dict) else None
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            costs.append(value)
    calls = execution.get('tool_calls')
    return {'source': 'execution.json' if execution_path.is_file() else 'run.json' if usage else None,
            'raw_usage_record_count': len(raw) if raw else None,
            'reasoning_tokens': sum(reasoning) if raw and len(reasoning) == len(raw) else None,
            'reasoning_reported_record_count': len(reasoning) if raw else None,
            'reasoning_reported_sum': sum(reasoning) if reasoning else None,
            'provider_reported_cost_usd': sum(costs) if raw and len(costs) == len(raw) else None,
            'cost_note': 'pi/provider catalog-reported estimate, not an invoice; absent measurements remain null.',
            'tool_call_count': len(calls) if isinstance(calls, list) else None,
            'tool_call_counts': dict(Counter(c.get('tool') for c in calls if c.get('tool'))) if isinstance(calls, list) else None,
            'model_response_count': execution.get('model_response_count', run.get('model_response_count')),
            'content_policy': 'Only structured usage and tool names/counts are inspected; no message or tool-result content is exported.'}


def audit_run(meta, cache):
    run = read_json(meta)
    work = meta.parent/'work'
    request_path = meta.parent/'request.json'
    record = {'run_id': run['id'], 'status_observed': run.get('status'), 'audited_at': now(),
              'provisional': run.get('status') in ACTIVE_STATUSES,
              'input_snapshot_present': request_path.is_file(), 'immutable_input_changes': [],
              'immutable_input_check': None, 'source_presence': None, 'dependency_versions': None,
              'needs_render_recovery': False, 'usage_observations': None, 'errors': []}
    request = {}
    if request_path.is_file():
        try:
            request = read_json(request_path)
            inputs = audit_inputs(work, request)
            record['immutable_input_changes'] = inputs.pop('changes')
            record['immutable_input_check'] = inputs
        except Exception as error:
            record['errors'].append({'phase': 'immutable_inputs', 'message': str(error)})
    if work.is_dir():
        try:
            source = source_presence(work, run['track'], request)
            record['source_presence'] = source
            record['needs_render_recovery'] = (run.get('status') == 'generation_failed' and run['track'] == 'video'
                                              and source['has_authored_source'] and source['entry_present']
                                              and not source['root_changed'])
            if record['needs_render_recovery']:
                record['recovery_note'] = 'Source changed outside src/Root.tsx. Inspect Main composition and render existing source; this flag does not prove the implementation is complete.'
        except Exception as error:
            record['errors'].append({'phase': 'source_presence', 'message': str(error)})
        try:
            record['dependency_versions'] = dependency_versions(work, run['track'], cache)
        except Exception as error:
            record['errors'].append({'phase': 'dependency_versions', 'message': str(error)})
    try:
        record['usage_observations'] = usage_observations(meta, run)
    except Exception as error:
        record['errors'].append({'phase': 'usage_metadata', 'message': str(error)})
    return record


def audit_all():
    records = {}
    errors = []
    cache = {}
    for meta in sorted((ROOT/'runs').glob('*/*/*/run-*/run.json')):
        try:
            record = audit_run(meta, cache)
            records[record['run_id']] = record
        except Exception as error:
            errors.append({'metadata_path': str(meta.relative_to(ROOT)), 'message': str(error)})
    summary = {'runs_observed': len(records), 'provisional_runs': sum(r['provisional'] for r in records.values()),
               'runs_with_input_changes': sum(bool(r['immutable_input_changes']) for r in records.values()),
               'render_recovery_candidates': sum(r['needs_render_recovery'] for r in records.values()),
               'runs_with_audit_errors': sum(bool(r['errors']) for r in records.values())}
    atomic_json(ROOT/'data/audits.json', {'schema_version': '1.0', 'updated_at': now(), 'summary': summary,
                                        'runs': records, 'errors': errors})
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watch', action='store_true')
    parser.add_argument('--interval', type=float, default=30)
    args = parser.parse_args()
    while True:
        try:
            print(json.dumps({'audit': audit_all(), 'at': now()}), flush=True)
        except Exception as error:
            print(json.dumps({'error': str(error), 'at': now()}), flush=True)
        if not args.watch:
            break
        time.sleep(max(1, args.interval))
