"""Run the real PS launcher against local fakes, never SQL/SMTP/Telegram/broker."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import pytest

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.skipif(os.name!='nt',reason='Windows process-tree regression')
@pytest.mark.parametrize('code,recovery_date',[(0,None),(7,None),(0,'2026-11-18')])
def test_launcher_finishes_and_notifies_while_persistent_child_survives(tmp_path,code,recovery_date):
    workspace=tmp_path/'workspace';workspace.mkdir()
    (workspace/'scripts').mkdir()
    (workspace/'batch.yaml').write_text('us_pipeline:\n  enabled: true\n  log_file: batch.log\n',encoding='utf-8')
    (workspace/'test.env').write_text('',encoding='utf-8')
    (workspace/'scripts/send_batch_email.py').write_text(
        "import json,sys\nfrom pathlib import Path\n"
        "Path('notification.json').write_text(json.dumps(sys.argv[1:]))\n"
        "print('LOCAL_NOTIFIER_CALLED')\n",encoding='utf-8')
    marker='alpha-forward-launcher-persistent-test'
    child_code=f'import time; marker={marker!r}; time.sleep(60)'
    (workspace/'fake_runner.py').write_text(
        'import json,sys,subprocess\nfrom pathlib import Path\n'
        'Path("runner_args.json").write_text(json.dumps(sys.argv[1:]))\n'
        f'child=subprocess.Popen([sys.executable,"-c",{child_code!r}],stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)\n'
        'Path("child.json").write_text(json.dumps({"pid":child.pid}))\n'
        'print("runner done",flush=True)\nprint("stderr captured",file=sys.stderr,flush=True)\n'
        f'raise SystemExit({code})\n',encoding='utf-8')
    shell=shutil.which('powershell.exe');assert shell
    started=time.monotonic()
    try:
        result=subprocess.run([shell,'-NoProfile','-ExecutionPolicy','Bypass','-File',
            str(ROOT/'scripts/windows/forward_pit_launcher.ps1'),'-BatchName','us_pipeline',
            '-WorkspacePath',str(workspace),'-PythonExePath',sys.executable,
            '-RunnerModule','fake_runner','-EnvFilePath',str(workspace/'test.env'),'-Force',
            *(['-RecoverySessionDate',recovery_date] if recovery_date else [])],
            cwd=workspace,capture_output=True,text=True,errors='replace',timeout=25)
        assert result.returncode==code,(result.stdout,result.stderr)
        runner_args=json.loads((workspace/'runner_args.json').read_text())
        if recovery_date:
            assert runner_args[-2:]==['--us-pipeline-recovery-date',recovery_date]
        else:
            assert '--us-pipeline-recovery-date' not in runner_args
        assert time.monotonic()-started<25
        child=json.loads((workspace/'child.json').read_text())['pid']
        import psutil
        p=psutil.Process(child)
        assert p.is_running() and p.cmdline()[-1]==child_code
        args=json.loads((workspace/'notification.json').read_text())
        assert args[args.index('--status')+1]==('OK' if code==0 else 'ERROR')
        assert args[args.index('--exit-code')+1]==str(code)
        logs=(workspace/'batch.log').read_text(encoding='utf-8-sig')
        assert 'FIN us_pipeline' in logs and 'NOTIFY LOCAL_NOTIFIER_CALLED' in logs
        assert 'stderr captured' in logs
    finally:
        file=workspace/'child.json'
        if file.exists():
            import psutil
            try:
                child=psutil.Process(json.loads(file.read_text())['pid'])
                if child.cmdline()[-1]==child_code:
                    child.kill();child.wait(timeout=10)
            except psutil.NoSuchProcess:
                pass
