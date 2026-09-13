# Installe toutes les tâches Forward PIT activées dans batch.yaml.
[CmdletBinding()]
param(
    [string]$WorkspacePath,
    [string]$PythonExePath,
    [ValidateSet('Interactive','System')][string]$RunAs='Interactive'
)
$ErrorActionPreference='Stop'; Set-StrictMode -Version Latest
if (-not $WorkspacePath) { $WorkspacePath=Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$workspace=(Resolve-Path -LiteralPath $WorkspacePath).Path
if (-not $PythonExePath) { $PythonExePath=Join-Path $workspace '.venv\Scripts\python.exe' }
$python=(Resolve-Path -LiteralPath $PythonExePath).Path
$configPath=Join-Path $workspace 'batch.yaml'
$pyCode=@'
import json, sys, yaml
from service.forward_pit.batch import HANDLERS
cfg = yaml.safe_load(open(sys.argv[1], encoding="utf-8")) or {}
print(json.dumps([name for name in HANDLERS if (cfg.get(name) or {}).get("enabled", False)]))
'@
Push-Location $workspace
try { $names=((& $python -c $pyCode $configPath) | Out-String).Trim() | ConvertFrom-Json } finally { Pop-Location }
foreach ($name in $names) {
    & (Join-Path $PSScriptRoot 'install_forward_pit_task.ps1') -BatchName $name -WorkspacePath $workspace -PythonExePath $python -RunAs $RunAs
}
Write-Host ("{0} tâche(s) Forward PIT active(s) installée(s)." -f @($names).Count) -ForegroundColor Green
