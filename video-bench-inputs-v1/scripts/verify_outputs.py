#!/usr/bin/env python3
"""Check technical media outputs only. Requires ffprobe; no aesthetic scoring."""
import argparse,json,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('project',type=Path);a=p.parse_args()
c=json.loads((a.project/'case.config.json').read_text());v=a.project/'out/video.mp4';errors=[]
def probe(file):return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(file)]))
if not v.exists():errors.append('missing out/video.mp4')
else:
 j=probe(v);streams=[s for s in j['streams'] if s['codec_type']=='video']
 if not streams:errors.append('no video stream')
 else:
  s=streams[0];num,den=map(int,s['avg_frame_rate'].split('/'));fps=num/den if den else 0
  if (s['width'],s['height'])!=(c['width'],c['height']):errors.append('wrong dimensions')
  if abs(fps-c['fps'])>.01:errors.append('wrong fps')
  expected=c['duration_frames']/c['fps']
  if abs(float(j['format']['duration'])-expected)>max(.1,2/c['fps']):errors.append('wrong duration')
if c.get('alpha_required'):
 f=a.project/'out/overlay.mov'
 if not f.exists():errors.append('missing transparent master')
 else:
  s=next((s for s in probe(f)['streams'] if s['codec_type']=='video'),{})
  if s.get('codec_name')!='prores' or not s.get('pix_fmt','').startswith('yuva'):errors.append('master lacks expected ProRes alpha format')
for f in ['design-plan.md','implementation.md','out/poster.png']:
 if not (a.project/f).exists():errors.append('missing '+f)
if len(list((a.project/'out/frames').glob('*.png')))<6:errors.append('need at least six frame PNGs')
print(json.dumps({'technical_pass':not errors,'errors':errors,'semantic_and_aesthetic_checks':'manual review required'},indent=2));sys.exit(bool(errors))
