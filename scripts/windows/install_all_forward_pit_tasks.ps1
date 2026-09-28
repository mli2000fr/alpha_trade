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
# Priorité au venv local, repli sur l'interpréteur du PATH (installation globale).
function Resolve-AlphaTradePythonExe {
    param(
        [Parameter(Mandatory=$true)][string]$Workspace,
        [string]$RequestedPythonExePath
    )
    if ($RequestedPythonExePath) {
        if (-not (Test-Path -LiteralPath $RequestedPythonExePath)) {
            throw "Python introuvable: $RequestedPythonExePath"
        }
        return (Resolve-Path -LiteralPath $RequestedPythonExePath).Path
    }
    $candidates = @(
        (Join-Path $Workspace '.venv\Scripts\python.exe'),
        (Join-Path $Workspace 'venv\Scripts\python.exe'),
        (Join-Path $Workspace '.python\Scripts\python.exe')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand) { return $pythonCommand.Source }
    $pyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyLauncher) { return $pyLauncher.Source }
    throw 'Aucun interpréteur Python exploitable trouvé. Fournir -PythonExePath ou créer .venv\Scripts\python.exe.'
}
$python=Resolve-AlphaTradePythonExe -Workspace $workspace -RequestedPythonExePath $PythonExePath
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
