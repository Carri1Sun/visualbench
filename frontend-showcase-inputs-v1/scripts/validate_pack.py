#!/usr/bin/env python3
from pathlib import Path
import json, hashlib, xml.etree.ElementTree as ET
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'manifest.json').read_text())
cases=manifest['cases']
assert len(cases)==20
assert sorted(c['number'] for c in cases)==list(range(1,21))
assert len({c['id'] for c in cases})==20
for p in root.rglob('*.json'):json.loads(p.read_text())
for p in root.rglob('*.svg'):ET.parse(p)
for c in cases:
    folder=root/'cases'/c['id']
    for name in ['case.json','SOURCE.md','prompt.en.txt','prompt.zh.txt','short.en.txt','short.zh.txt']:
        assert (folder/name).is_file(),(c['id'],name)
        assert (folder/name).stat().st_size>0
    for a in c['input_files']:assert (folder/a).is_file(),(c['id'],a)
    for lang in ['en','zh']:assert (root/'ready-prompts'/f'{c["id"]}.{lang}.txt').is_file()
    assert (root/'starters'/c['starter']/'index.html').is_file()
for line in (root/'SHA256SUMS.txt').read_text().splitlines():
    digest,name=line.split('  ',1)
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
print(f'PASS: {len(cases)} cases, JSON and SVG syntax, asset paths, prompts, templates and checksums.')
