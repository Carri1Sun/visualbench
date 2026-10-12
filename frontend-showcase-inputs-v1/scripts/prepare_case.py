#!/usr/bin/env python3
"""Prepare inputs only; does not call a model."""
from pathlib import Path
import argparse, json, shutil

parser=argparse.ArgumentParser()
parser.add_argument('case_id')
parser.add_argument('--dest',required=True)
parser.add_argument('--lang',choices=['en','zh'],default='en')
parser.add_argument('--variant',choices=['full','short'],default='full')
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'manifest.json').read_text())
case=next((c for c in manifest['cases'] if c['id']==args.case_id),None)
if case is None:parser.error('Unknown case id; see cases.csv')
dest=Path(args.dest).expanduser().resolve()
if dest==root or root.is_relative_to(dest):parser.error('Destination may not contain/replace the input pack')
if dest.exists() and any(dest.iterdir()):parser.error('Destination must be absent or empty, to preserve prior runs')
dest.mkdir(parents=True,exist_ok=True)
source=root/'cases'/case['id']
if (source/'assets').exists():shutil.copytree(source/'assets',dest/'assets')
shutil.copytree(root/'vendor',dest/'vendor')
shutil.copy2(root/'starters'/case['starter']/'index.html',dest/'index.html')
system=(root/'common'/f'system.{args.lang}.txt').read_text()
user=(source/f"{'prompt' if args.variant=='full' else 'short'}.{args.lang}.txt").read_text()
for name in case['input_files']:
    body=(source/name).read_text()
    user+=f'\nINPUT FILE: {name}\n```{Path(name).suffix.lstrip(".")}\n{body}```\n'
request={'case_id':case['id'],'language':args.lang,'variant':args.variant,'system':system,'user':user,'output_files':['plan.json','artifact.html'],'calls_model':False}
(dest/'request.json').write_text(json.dumps(request,ensure_ascii=False,indent=2)+'\n')
(dest/f'INPUT.{args.lang}.txt').write_text(system+'\nTASK / 任务\n'+user)
(dest/'RUN-METADATA.json').write_text(json.dumps({'case_id':case['id'],'model':None,'model_parameters':{},'run_number':None,'mode':'one_completion_or_disclosed_agent','language':args.lang,'variant':args.variant,'tool_permissions':None,'repairs':[],'status':'inputs_prepared'},ensure_ascii=False,indent=2)+'\n')
print(f'Prepared {case["id"]} at {dest}')
print(f'Read INPUT.{args.lang}.txt; generate plan.json and artifact.html.')
