#!/usr/bin/env python3
"""Verify all packaged input bytes; optional --media checks require ffprobe."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--media',action='store_true');a=p.parse_args()
m=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'));errors=[];count=0;media_count=0
if len(m['cases'])!=20:errors.append('Expected exactly 20 cases')
if len({c['id'] for c in m['cases']})!=20:errors.append('Case ids must be unique')
for c in m['cases']:
 d=ROOT/'cases'/c['id'];base=(d/'assets').resolve()
 for name in ['prompt.en.md','prompt.zh.md','SOURCE.md','task.json']:
  if not (d/name).is_file():errors.append(f"{c['id']}: missing {name}")
 if round(c['duration_seconds']*c['fps'])!=c['duration_frames']:errors.append(c['id']+': frame mismatch')
 for f in c['inputs']:
  path=(base/f['path']).resolve();count+=1
  if base not in path.parents:errors.append(c['id']+': unsafe input path');continue
  if not path.is_file():errors.append(c['id']+': missing '+f['path']);continue
  b=path.read_bytes()
  if not b or len(b)!=f['bytes'] or hashlib.sha256(b).hexdigest()!=f['sha256']:errors.append(c['id']+': byte/hash mismatch '+f['path'])
  try:
   if path.suffix=='.json':json.loads(b)
   if path.suffix in ('.svg','.gpx'):ET.fromstring(b)
   if a.media and path.suffix in ('.mp4','.webm','.wav','.mov'):
    j=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(path)]));media_count+=1
    if not j.get('streams') or float(j['format'].get('duration',0))<=0:errors.append('Invalid media '+str(path))
  except Exception as e:errors.append(f'{path}: {e}')
# Optional full-package checksum manifest, excludes itself and generated run outputs.
checks=ROOT/'CHECKSUMS.sha256'
if checks.exists():
 for line in checks.read_text().splitlines():
  sha,name=line.split('  ',1);q=ROOT/name
  if not q.is_file() or hashlib.sha256(q.read_bytes()).hexdigest()!=sha:errors.append('Package checksum mismatch '+name)
print(json.dumps({'ok':not errors,'cases':len(m['cases']),'input_files_checked':count,'media_files_checked':media_count,'errors':errors},ensure_ascii=False,indent=2));sys.exit(bool(errors))
