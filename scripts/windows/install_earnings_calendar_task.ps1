# install_earnings_calendar_task.ps1
#
# Installe la tâche planifiée Windows « AlphaTrade-EarningsCalendarSync » qui
# exécute earnings_calendar_launcher.ps1 AUTOMATIQUEMENT (sans lancement
# manuel) aux heures définies dans config.yaml → earnings_calendar_sync.run_hours :
#   - run_hours: "3"    → à 03h00
#   - run_hours: "4,9"  → à 04h00 et 09h00
# run_days (0=dimanche … 6=samedi) OPTIONNEL :
#   - renseigné (ex. "0,3,5") → déclencheurs HEBDOMADAIRES ces jours-là
#     uniquement (le launcher garde aussi le filet run_days → ligne SKIP).
#   - vide/absent → déclencheurs QUOTIDIENS (comportement historique).
# L'univers est piloté par earnings_calendar_sync.symbols_file (même fichier
# que analyst_snapshot_collect) avec repli --symbol-source active-tradable.
#
# Usage :
#   powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_earnings_calendar_task.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\windows\install_earnings_calendar_task.ps1 -RunAs System
#
# `-RunAs System` = s'exécute même quand personne n'est connecté.
# `-RunAs Interactive` (défaut) = s'exécute dans la session de l'utilisateur courant.
[CmdletBinding()]
param(
    [string]$TaskName = 'AlphaTrade-EarningsCalendarSync',
    [string]$WorkspacePath,
    [string]$PythonExePath,
    [string]$LogFile,
    [string]$RunHours,
    [string]$RunDays,
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

function Read-EarningsCalendarConfig {
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
    $pyCode = 'import json,sys,yaml; cfg=yaml.safe_load(open(sys.argv[1],encoding=''utf-8'')) or {}; print(json.dumps(cfg.get(''earnings_calendar_sync'') or {}))'
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
$launcherPath = Join-Path $PSScriptRoot 'earnings_calendar_launcher.ps1'
if (-not (Test-Path -LiteralPath $launcherPath)) {
    throw "Launcher PowerShell introuvable: $launcherPath"
}

# ── Lecture config.yaml (run_hours + log_file) via l'interpréteur Python ──
$resolvedPython = Resolve-AlphaTradePythonExe -Workspace $resolvedWorkspace -RequestedPythonExePath $PythonExePath
$cfg = Read-EarningsCalendarConfig -Workspace $resolvedWorkspace -PythonExe $resolvedPython

$hoursRaw = $RunHours
if (-not $hoursRaw) {
    if ($cfg -and ($cfg.PSObject.Properties.Name -contains 'run_hours') -and $cfg.run_hours) {
        $hoursRaw = [string]$cfg.run_hours
    } else {
        $hoursRaw = '3'
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
    $hours = @(3)
}

# ── run_days (facultatif) : jours de la semaine 0=dimanche … 6=samedi ──
#    Renseigné (ex. "0,3,5") → déclencheurs HEBDOMADAIRES ces jours-là.
#    Vide/absent → déclencheurs QUOTIDIENS (comportement historique).
$daysRaw = $RunDays
if (-not $daysRaw) {
    if ($cfg -and ($cfg.PSObject.Properties.Name -contains 'run_days') -and $cfg.run_days) {
        $daysRaw = [string]$cfg.run_days
    } else {
        $daysRaw = ''
    }
}
$days = @(
    $daysRaw -split ',' |
        ForEach-Object { $_.Trim() } |
        Where-Object { $_ -match '^\d$' } |
        ForEach-Object { [int]$_ } |
        Where-Object { $_ -ge 0 -and $_ -le 6 } |
        Sort-Object -Unique
)
$dayNames = @('dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi')

$effectiveLogFile = $LogFile
if (-not $effectiveLogFile) {
    if ($cfg -and ($cfg.PSObject.Properties.Name -contains 'log_file') -and $cfg.log_file) {
        $effectiveLogFile = [string]$cfg.log_file
    } else {
        $effectiveLogFile = 'log/batch/earnings_calendar.txt'
    }
}
if (-not [IO.Path]::IsPathRooted($effectiveLogFile)) {
    $effectiveLogFile = Join-Path $resolvedWorkspace $effectiveLogFile
}

# ── Triggers aux heures configurées ──
#    run_days renseigné → HEBDOMADAIRES (ces jours uniquement).
#    run_days vide → QUOTIDIENS (comportement historique).
if ($days.Count -gt 0) {
    $dayOfWeek = @($days | ForEach-Object { [DayOfWeek]$_ })
    $triggers = @($hours | ForEach-Object {
        New-ScheduledTaskTrigger -Weekly -DaysOfWeek $dayOfWeek -At (Get-Date -Hour $_ -Minute 0 -Second 0)
    })
} else {
    $triggers = @($hours | ForEach-Object {
        New-ScheduledTaskTrigger -Daily -At (Get-Date -Hour $_ -Minute 0 -Second 0)
    })
}

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
    # RunLevel limité (défaut) : suffisant pour la sync et évite d'exiger
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
Write-Host "Heures      : $($hours -join ', ')"
if ($days.Count -gt 0) {
    $dayLabels = @($days | ForEach-Object { $dayNames[$_] })
    Write-Host "Jours       : $($days -join ',') ($($dayLabels -join ', '))"
    Write-Host "Planif      : hebdomadaire (uniquement ces jours — le launcher garde le filet run_days → SKIP)"
} else {
    Write-Host "Planif      : tous les jours (run_days vide/absent)"
}
Write-Host "RunAs       : $RunAs"
Write-Host "Log statut  : $effectiveLogFile"
Write-Host ""
Write-Host "Pour vérifier le statut : schtasks /query /tn $TaskName /v /fo LIST"
