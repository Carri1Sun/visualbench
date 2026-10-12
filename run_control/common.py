"""Frozen inputs, public catalog, and atomic result storage."""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((Path(__file__).resolve().parent / 'config.json').read_text())
PACKS = {'frontend': ROOT / 'frontend-showcase-inputs-v1', 'video': ROOT / 'video-bench-inputs-v1'}

def now():
    return datetime.now(timezone.utc).isoformat()

def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f'.{os.getpid()}.{__import__("threading").get_ident()}.tmp')
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    tmp.replace(path)

def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def public_path(path):
    return '/results/' + str(Path(path).relative_to(ROOT))

def all_cases():
    return [(track, case) for track, pack in PACKS.items() for case in json.loads((pack / 'manifest.json').read_text())['cases']]

def protocol():
    return {
        'round_id': CONFIG['round_id'], 'language': 'zh', 'variant': 'full', 'repetitions': 3,
        'harness': 'pi 0.99.2', 'mode': 'independent_agent_session',
        'thinking_requested': 'mixed: initial max; remaining Astra/Sol high' if CONFIG.get('thinking_policy') else 'max',
        'thinking_effective': 'Recorded per run from native Pi session events',
        'thinking_defaults_by_model': {m['id']: m['thinking'] for m in CONFIG['models']},
        'thinking_policy': CONFIG.get('thinking_policy'),
        'generation_timeout_seconds': CONFIG['generation_timeout_seconds'],
        'render_timeout_seconds': CONFIG['render_timeout_seconds'],
        'workers_per_model': CONFIG['workers_per_model'], 'render_workers': CONFIG['render_workers'],
        'execution_changes_path': '/data/execution-changes.json',
        'temperature': None, 'seed': None, 'token_limit': None, 'cost_limit': None,
        'tools': ['read', 'bash', 'edit', 'write'], 'skills': [],
        'extensions': [], 'context_files': False, 'external_assets': False,
        'dependencies': 'Remotion 4.0.532 / React 19.0.0 / TypeScript 5.8.3; original lockfile',
        'dependency_setup': 'shared, preinstalled, excluded from generation duration',
        'repair_policy': 'Agent may debug within one 45-minute session. Curator never rewrites model source. External capture/build does not repair code. Transport retries remain recorded.',
        'isolation': 'Fresh working directory and session; shared read-only-by-policy dependencies; tools run with local user permissions. This is not an OS sandbox.',
        'capture': {'desktop': [1280, 800], 'mobile': [390, 844], 'wait_seconds': 2, 'record_seconds': 8},
        'scope_note': '40 frozen tasks; frontend full variant. Input modes are descriptive, not a controlled guidance-strength experiment. Mobile adaptation applies to frontend product cases.',
        'capability_note': 'Local pi catalog marks GLM 5.3 text-only. This capability difference is retained and disclosed; no surrogate vision model is used.',
        'usage_note': 'Usage is reported by pi/provider; provider prices may be catalog estimates, not invoices. Unknown sampling/cost values remain null.',
        'input_manifest_sha256': {track: sha256(pack / 'manifest.json') for track, pack in PACKS.items()},
        'lockfile_sha256': sha256(PACKS['video'] / 'starter/remotion/package-lock.json'),
    }

def init():
    cases = []
    for track, c in all_cases():
        pack = PACKS[track]
        src = pack / 'cases' / c['id']
        prompt = (src / ('prompt.zh.txt' if track == 'frontend' else 'prompt.zh.md')).read_text()
        system = (pack / ('common/system.zh.txt' if track == 'frontend' else 'COMMON_INSTRUCTIONS.zh.md')).read_text()
        assets = [{'name': str(p.relative_to(src)), 'url': '/inputs/' + track + '/' + str(p.relative_to(pack)), 'sha256': sha256(p)} for p in sorted((src / 'assets').rglob('*')) if p.is_file()] if (src / 'assets').exists() else []
        cases.append({
            'id': track + '/' + c['id'], 'case_id': c['id'], 'track': track,
            'title': c['title_zh'], 'title_en': c['title_en'], 'number': c['number'],
            'category': c.get('category', 'motion'), 'input_mode': c.get('input_mode', c.get('material_requirement')),
            'description': c.get('brief_zh', prompt[:200]), 'prompt': system + '\n\n' + prompt,
            'source': c.get('source_url'), 'source_note': c.get('adaptation_note_zh', c.get('changes_from_source')),
            'assets': assets, 'width': c.get('width', 1280), 'height': c.get('height', 800),
            'duration_seconds': c.get('duration_seconds'), 'fps': c.get('fps'),
            'alpha_required': c.get('alpha_required', False), 'interaction_actions': c.get('interaction_actions', []),
        })
    atomic_json(ROOT / 'data/catalog.json', {'schema_version': '1.0', 'protocol': protocol(), 'models': CONFIG['models'], 'cases': cases})
    for track, c in all_cases():
        for m in CONFIG['models']:
            for n in range(1, CONFIG['repetitions'] + 1):
                d = ROOT / 'runs' / track / m['id'] / c['id'] / f'run-{n}'
                meta = d / 'run.json'
                if meta.exists():
                    continue
                atomic_json(meta, {
                    'id': f'{track}/{m["id"]}/{c["id"]}/run-{n}', 'case_id': c['id'],
                    'case_key': track + '/' + c['id'], 'track': track, 'model_id': m['id'],
                    'provider': m['provider'], 'model': m['model'], 'run_number': n,
                    'thinking_requested': m['thinking'], 'thinking_effective': None,
                    'variant': 'full', 'language': 'zh', 'status': 'queued', 'phase': 'queued',
                    'artifact_path': None, 'plan_path': None, 'screenshot_path': None, 'video_path': None,
                    'code_path': None, 'metadata_path': public_path(meta), 'console_path': None,
                    'duration_ms': None, 'usage': None, 'error': None,
                    'started_at': None, 'finished_at': None, 'attempts': [], 'repairs': [],
                })
    publish()

def publish():
    runs = [json.loads(p.read_text()) for p in sorted((ROOT / 'runs').glob('*/*/*/run-*/run.json'))]
    atomic_json(ROOT / 'results/index.json', {'schema_version': '1.0', 'updated_at': now(), 'protocol': protocol(), 'runs': runs})

if __name__ == '__main__':
    init()
    print('Initialized 40 cases and 600 independent run slots.')
