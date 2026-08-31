# install_analyst_snapshot_task.ps1
#
# Installe la tâche planifiée Windows « AlphaTrade-AnalystSnapshot » qui
# exécute analyst_snapshot_launcher.ps1 AUTOMATIQUEMENT (sans lancement
# manuel) aux heures définies dans config.yaml → analyst_snapshot_collection.run_hours :
#   - run_hours: "18"   → tous les jours à 18h00 America/New_York (après clôture US)
#   - run_hours: "3,14" → tous les jours à 03h00 et 14h00
#
# La collecte est RESEARCH ONLY (estimates/targets/recommendations Yahoo,
# append-only PIT dans MySQL). Le launcher relance avec `--resume` (idempotent).
#
# Usage :
#   powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_analyst_snapshot_task.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_analyst_snapshot_task.ps1 -RunAs System
#
# `-RunAs System` = s'exécute même quand personne n'est connecté.
# `-RunAs Interactive` (défaut) = s'exécute dans la session de l'utilisateur courant.
[CmdletBinding()]
param(
    [string]$TaskName = 'AlphaTrade-AnalystSnapshot',
    [string]$WorkspacePath,
    [string]$PythonExePath,
    [string]$LogFile,
    [string]$RunHours,
    [ValidateSet('Interactive', 'System')]
    [string]$RunAs = 'Interactive',
    [string]$UserId = $(if ($env:USERDOMAIN) { "$($env:USERDOMAIN)\$($env:USERNAME)" } else { $env:USERNAME })
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

# NB : $PSScriptRoot n'est pas disponible dans les valeurs par défaut des
# paramètres (évaluées pendant le binding, avant l'exécution) → calcul ici.
if (-not $WorkspacePath) {
    $WorkspacePath = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}

function Resolve-AlphaTradePythonExe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Workspace,
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
    if ($pythonCommand) {
        return $pythonCommand.Source
    }
    $pyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        return $pyLauncher.Source
    }
    throw 'Aucun interpréteur Python exploitable trouvé. Fournir -PythonExePath ou créer .venv\Scripts\python.exe.'
}

function Read-AnalystSnapshotConfig {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Workspace,
        [Parameter(Mandatory = $true)]
        [string]$PythonExe
    )
    $configPath = Join-Path $Workspace 'config.yaml'
    if (-not (Test-Path -LiteralPath $configPath)) {
        return $null
    }
    # NB : code Python en guillemets SIMPLES uniquement — PowerShell 5.1
    # supprime les guillemets doubles d'une variable passée à un exe natif.
    $pyCode = 'import json,sys,yaml; cfg=yaml.safe_load(open(sys.argv[1],encoding=''utf-8'')) or {}; print(json.dumps(cfg.get(''analyst_snapshot_collection'') or {}))'
    try {
        $jsonOut = (& $PythonExe -c $pyCode $configPath 2>$null | Out-String).Trim()
    } catch {
        return $null
    }
    if (-not $jsonOut) {
        return $null
    }
    try {
        return ($jsonOut | ConvertFrom-Json)
    } catch {
        return $null
    }
}

$resolvedWorkspace = (Resolve-Path -LiteralPath $WorkspacePath).Path
$launcherPath = Join-Path $PSScriptRoot 'analyst_snapshot_launcher.ps1'
if (-not (Test-Path -LiteralPath $launcherPath)) {
    throw "Launcher PowerShell introuvable: $launcherPath"
}

# ── Lecture config.yaml (run_hours + log_file) via l'interpréteur Python ──
$resolvedPython = Resolve-AlphaTradePythonExe -Workspace $resolvedWorkspace -RequestedPythonExePath $PythonExePath
$cfg = Read-AnalystSnapshotConfig -Workspace $resolvedWorkspace -PythonExe $resolvedPython

$hoursRaw = $RunHours
if (-not $hoursRaw) {
    if ($cfg -and ($cfg.PSObject.Properties.Name -contains 'run_hours') -and $cfg.run_hours) {
        $hoursRaw = [string]$cfg.run_hours
    } else {
        $hoursRaw = '18'
    }
}
$hours = @(
    $hoursRaw -split ',' |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ -match '^\d{1,2}$' } |
        ForEach-Object { [int]$_ } |
        Where-Object { $_ -ge 0 -and $_ -le 23 } |
        Sort-Object -Unique
)
if ($hours.Count -eq 0) {
    $hours = @(18)
}

$effectiveLogFile = $LogFile
if (-not $effectiveLogFile) {
    if ($cfg -and ($cfg.PSObject.Properties.Name -contains 'log_file') -and $cfg.log_file) {
        $effectiveLogFile = [string]$cfg.log_file
    } else {
        $effectiveLogFile = 'log/batch/analyst_snapshots.txt'
    }
}
if (-not [IO.Path]::IsPathRooted($effectiveLogFile)) {
    $effectiveLogFile = Join-Path $resolvedWorkspace $effectiveLogFile
}

# ── Triggers quotidiens aux heures configurées ──
$triggers = @($hours | ForEach-Object {
    New-ScheduledTaskTrigger -Daily -At (Get-Date -Hour $_ -Minute 0 -Second 0)
})

# ── Action : powershell -File <launcher> ──
$argumentList = @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', ('"{0}"' -f $launcherPath),
    '-WorkspacePath', ('"{0}"' -f $resolvedWorkspace),
    '-PythonExePath', ('"{0}"' -f $resolvedPython),
    '-LogFile', ('"{0}"' -f $effectiveLogFile)
)
$actionArguments = $argumentList -join ' '

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $actionArguments -WorkingDirectory $resolvedWorkspace
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 12)
$principal = if ($RunAs -eq 'System') {
    New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
} else {
    # RunLevel limité (défaut) : suffisant pour la collecte et évite d'exiger
    # des droits administrateur à l'installation (mode interactif).
    New-ScheduledTaskPrincipal -UserId $UserId -LogonType Interactive
}

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal | Out-Null

Write-Host "Task Scheduler installé: $TaskName" -ForegroundColor Green
Write-Host "Workspace   : $resolvedWorkspace"
Write-Host "Heures      : $($hours -join ', ') (tous les jours, heure locale de la machine)"
Write-Host "RunAs       : $RunAs"
Write-Host "Log statut  : $effectiveLogFile"
Write-Host ""
Write-Host "⚠️ L'heure des triggers suit la timezone de la machine. Pour un déclenchement"
Write-Host "   'après clôture US' en America/New_York, régler `run_hours` dans config.yaml"
Write-Host "   et configurer la timezone du planificateur (ou lancer manuellement via le launcher)."
Write-Host ""
Write-Host "Pour vérifier le statut : schtasks /query /tn $TaskName /v /fo LIST"
