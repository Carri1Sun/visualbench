"""Install the frozen runtime and prewarm clean independent video workspaces."""
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from common import ROOT, PACKS, init

def main():
    runtime=ROOT/'.runtime/remotion';runtime.mkdir(parents=True,exist_ok=True)
    for name in ('package.json','package-lock.json'):
        shutil.copy2(PACKS['video']/'starter/remotion'/name,runtime/name)
    if not (runtime/'node_modules/remotion/package.json').exists():
        subprocess.run(['npm','ci','--no-audit','--no-fund'],cwd=runtime,check=True)
    subprocess.run([str(runtime/'node_modules/.bin/remotion'),'browser','ensure'],cwd=ROOT,check=True)
    init()
    prepared=0
    for meta in sorted((ROOT/'runs/video').glob('*/*/run-*/run.json')):
        d=json.loads(meta.read_text());work=meta.parent/'work'
        if d['status']=='queued' and not work.exists():
            stage=Path(tempfile.mkdtemp(prefix='prepare-',dir=ROOT/'.runtime'))/'work'
            result=subprocess.run(['python3',str(PACKS['video']/'scripts/prepare_case.py'),d['case_id'],str(stage),'--language','zh'],capture_output=True,text=True)
            if result.returncode:raise RuntimeError(result.stderr)
            try:stage.rename(work);prepared+=1
            except OSError:
                if not work.exists():raise
            finally:shutil.rmtree(stage.parent,ignore_errors=True)
        if work.exists():
            for name,target in [('node_modules',runtime/'node_modules'),('.remotion',ROOT/'.remotion')]:
                if not (work/name).exists(): (work/name).symlink_to(target,target_is_directory=True)
    print(f'Prepared {prepared} clean video workspaces with shared frozen runtime.')

if __name__=='__main__': main()
