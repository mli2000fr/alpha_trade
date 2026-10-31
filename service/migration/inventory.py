"""Explicit project inventory, including uncommitted source and all ML trees."""
import hashlib
import os
from pathlib import Path
import platform
import re
import subprocess

SKIP_ROOT={'.git','.venv','.codex','.continue','.idea','.vscode','backups','tmp','htmlcov',
    '.pytest_cache','.ruff_cache','.hypothesis','.benchmarks','_norton_','catboost_info'}
SKIP_DIR={'__pycache__','.pytest_cache','.ruff_cache'}
TRANSIENT={'tmp','test_tmp','test-tmp','tests','smoke_tests','test-tmp','.locks'}


def excluded(relative):
    parts=relative.parts
    if not parts or parts[0] in SKIP_ROOT or parts[0].startswith('.venv'):return True
    if any(p in SKIP_DIR for p in parts):return True
    if relative.name.startswith(('.alpha_trade_migration','.alpha_trade_restore')):return True
    if relative.name.endswith(('.pyc','.pid','.lock')):return True
    if parts[0]=='artifacts' and len(parts)>1:
        if parts[1] in TRANSIENT|{'backups','migration_jobs'}:return True
        if relative.name in ('service_state.json','heartbeat.json'):return True
    return False


def category(relative):
    p=relative.parts
    if p[0]=='artifacts' and len(p)>1 and p[1].startswith('models'):return 'modeles'
    if p[0] in ('config','conf','prompt','prompts') or len(p)==1 and (relative.name.startswith('.env') or relative.suffix in ('.yaml','.yml','.toml','.ini')):return 'configuration'
    if p[0] in ('artifacts','outputs','log','logs','analyst_research'):return 'etats-et-archives'
    return 'application'


def scan(root):
    root=Path(root).resolve();result={k:[] for k in ('application','configuration','modeles','etats-et-archives')}
    def fail(error):raise error
    for current,dirs,files in os.walk(root,onerror=fail,followlinks=False):
        current=Path(current)
        for name in list(dirs):
            path=current/name;relative=path.relative_to(root)
            if excluded(relative):dirs.remove(name);continue
            if path.is_symlink() or path.is_junction():raise ValueError('Lien/jonction externe à traiter avant sauvegarde : '+str(relative))
        for name in sorted(files):
            path=current/name;relative=path.relative_to(root)
            if excluded(relative):continue
            if path.is_symlink() or not path.resolve().is_relative_to(root):raise ValueError('Fichier hors projet')
            stat=path.stat()
            result[category(relative)].append(dict(path=relative.as_posix(),size=stat.st_size,mtime_ns=stat.st_mtime_ns))
    return result


def installed_versions(root):
    import sys
    proc=subprocess.run([sys.executable,'-m','pip','freeze','--all'],capture_output=True,text=True,cwd=root,check=True)
    # Local editable paths are not valid installation requirements on another PC.
    requirements=[]
    unportable=0
    for line in proc.stdout.splitlines():
        if not line or line.startswith('#'):continue
        if not re.fullmatch(r'[A-Za-z0-9_.-]+==[A-Za-z0-9_.+!-]+',line):
            unportable+=1;continue
        requirements.append(line)
    return dict(python=platform.python_version(),system=platform.system(),machine=platform.machine(),
        requirements='\n'.join(requirements)+'\n',unportable_requirement_count=unportable)


def running_processes(root,*,allow_ui=True):
    import psutil
    root=Path(root).resolve();result=[]
    for process in psutil.process_iter(['pid','name','cmdline','exe']):
        if process.pid==os.getpid():continue
        try:
            cmd=process.info['cmdline'] or [];joined=' '.join(cmd)
            exe=process.info['exe'] or ''
            belongs=(bool(exe) and Path(exe).resolve().is_relative_to(root)) or str(root).casefold() in joined.casefold()
            if not belongs:
                try:belongs=Path(process.cwd()).resolve().is_relative_to(root)
                except (psutil.AccessDenied,psutil.NoSuchProcess):pass
            if not belongs:continue
            # An IDE/shell can be open in the workspace. Only workers and known
            # database clients can mutate the snapshot; inaccessible workers block.
            name=(process.info['name'] or '').lower()
            if not any(n in name for n in ('python','mysql','mariadb')):continue
            if process.ppid()==os.getpid() and (any(x in name for x in ('mysql','mariadb')) or cmd[1:4]==['-m','pip','freeze']):continue
            if allow_ui and ('streamlit' in joined or 'ihm/app.py' in joined.replace('\\','/')):continue
            result.append(dict(pid=process.pid,name=process.info['name']))
        except psutil.NoSuchProcess:continue
        except psutil.AccessDenied:result.append(dict(pid=process.pid,name='processus inaccessible'))
    return result


def enabled_tasks(root):
    """Read-only scheduler inventory. No disabling tasks or watcher services."""
    if os.name!='nt':return []
    script=r'''$ErrorActionPreference='Stop'; $r=$env:ALPHA_MIGRATION_SCAN_ROOT; $out=@();
    Get-ScheduledTask | ForEach-Object { $t=$_; if($t.Settings.Enabled) {
      foreach($a in $t.Actions) { if(($a.Execute -like "$r*") -or ($a.Arguments -like "*$r*") -or ($a.WorkingDirectory -like "$r*")) {
        $out+=@{task=($t.TaskPath+$t.TaskName);name='tâche planifiée active'};break
      }}
    }}; ConvertTo-Json -InputObject $out -Compress'''
    p=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',script],capture_output=True,timeout=30,
        text=True,encoding='utf-8',errors='replace',env=dict(os.environ,ALPHA_MIGRATION_SCAN_ROOT=str(Path(root).resolve())))
    if p.returncode:raise ValueError('Inventaire des tâches Windows inaccessible ; vérifier les droits')
    import json
    return json.loads(p.stdout or '[]')


def quiescent(root,*,allow_ui=True):
    return running_processes(root,allow_ui=allow_ui)+enabled_tasks(root)
