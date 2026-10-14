"""Start/resume local services without terminating ongoing evaluations."""
import argparse
import json
import os
import socket
import subprocess
from pathlib import Path
from common import ROOT, now

RUNTIME = ROOT/'.runtime'

def alive(pid):
    try: os.kill(pid,0); return True
    except (ProcessLookupError,PermissionError): return False

def spawn(name, cmd, cwd=ROOT):
    pidfile=RUNTIME/f'{name}.pid'
    if pidfile.exists() and alive(int(pidfile.read_text())):
        return int(pidfile.read_text())
    (RUNTIME/'logs').mkdir(parents=True,exist_ok=True)
    with (RUNTIME/'logs'/f'{name}.log').open('ab') as f:
        p=subprocess.Popen(cmd,cwd=cwd,stdin=subprocess.DEVNULL,stdout=f,stderr=subprocess.STDOUT,start_new_session=True)
    pidfile.write_text(str(p.pid));return p.pid

def status():
    result={'at':now(),'services':{}}
    for p in RUNTIME.glob('*.pid'):
        try: pid=int(p.read_text());result['services'][p.stem]={'pid':pid,'alive':alive(pid)}
        except ValueError: pass
    index=ROOT/'results/index.json'
    if index.exists():
        runs=json.loads(index.read_text())['runs'];counts={}
        for r in runs:counts[r['status']]=counts.get(r['status'],0)+1
        result['counts']=counts;result['total']=len(runs)
        result['active']=[{'id':r['id'],'phase':r.get('phase'),'started_at':r.get('started_at')} for r in runs if r['status'] in {'generating','rendering','running'}]
    print(json.dumps(result,ensure_ascii=False,indent=2))

def start(include_runner=False):
    services = [
        ('server',['python3','result_background/server.py','--port','4174']),
        ('resources',['python3','result_background/resource_server.py','--port','4180']),
        ('capture-server',['python3','result_background/server.py','--port','4175','--with-resources']),
        ('trajectory',['python3','-u','run_control/export_trajectories.py','--watch']),
        ('audit',['python3','-u','run_control/audit_outputs.py','--watch']),
        ('app',['npm','run','dev','--','--host','127.0.0.1']),
    ]
    if include_runner: services.append(('runner',['python3','-u','run_control/runner.py']))
    for name,cmd in services:
        print(name,spawn(name,cmd,ROOT/'result_display_frontend' if name=='app' else ROOT))
    runner_pid=RUNTIME/'runner.pid'
    if __import__('sys').platform=='darwin' and runner_pid.exists() and alive(int(runner_pid.read_text())):
        spawn('awake',['caffeinate','-i','-w',(RUNTIME/'runner.pid').read_text()])
    print('展示页 http://127.0.0.1:4173 · 数据4174 · 资源4180 · 独立捕获4175')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['start','status']);p.add_argument('--runner',action='store_true');a=p.parse_args()
    start(a.runner) if a.action=='start' else status()
