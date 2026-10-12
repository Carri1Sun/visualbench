#!/usr/bin/env python3
"""Make an isolated, model-facing project. Python 3 standard library only."""
from pathlib import Path
import argparse,json,shutil
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('case',help='Two-digit number or complete case id')
p.add_argument('destination',type=Path)
p.add_argument('--language',choices=['en','zh'],default='en')
a=p.parse_args()
manifest=json.loads((ROOT/'manifest.json').read_text(encoding='utf-8'))
matches=[c for c in manifest['cases'] if c['id']==a.case or str(c['number'])==a.case.lstrip('0')]
if len(matches)!=1:p.error('Unknown or ambiguous case; consult manifest.json')
c=matches[0];dest=a.destination.resolve();source=ROOT/'cases'/c['id']
if dest==ROOT or ROOT in dest.parents:p.error('Destination must be outside this immutable input package')
if dest.exists() and any(dest.iterdir()):p.error('Destination is not empty; will not overwrite an existing run')
shutil.copytree(ROOT/'starter/remotion',dest,dirs_exist_ok=True,ignore=shutil.ignore_patterns('node_modules','out','.cache','.DS_Store'))
if (source/'assets').is_dir():
 shutil.copytree(source/'assets',dest/'public/input',dirs_exist_ok=True)
else:
 (dest/'public/input').mkdir(parents=True,exist_ok=True)
shutil.copytree(ROOT/'shared/fonts',dest/'public/fonts',dirs_exist_ok=True)
config={k:c[k] for k in ['width','height','fps','duration_frames']};config['case_id']=c['id'];config['alpha_required']=c['alpha_required']
(dest/'case.config.json').write_text(json.dumps(config,indent=2)+'\n',encoding='utf-8')
# Source URLs stay in the curator package so a model does not see other creators' solutions.
worker={k:c[k] for k in ['id','number','title_zh','title_en','input_mode','width','height','fps','duration_frames','duration_seconds','alpha_required','inputs','checks']}
(dest/'TASK.json').write_text(json.dumps(worker,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
common=(ROOT/f'COMMON_INSTRUCTIONS.{a.language}.md').read_text(encoding='utf-8')
brief=(source/f'prompt.{a.language}.md').read_text(encoding='utf-8')
(dest/'PROMPT.md').write_text(common+'\n\n---\n\n'+brief,encoding='utf-8')
print(json.dumps({'case_id':c['id'],'project':str(dest),'agent_entry':str(dest/'PROMPT.md'),'next':['npm ci','npm run typecheck','npm run studio']},ensure_ascii=False,indent=2))
