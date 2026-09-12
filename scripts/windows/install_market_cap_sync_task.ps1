# Installe AlphaTrade-MarketCapSync aux heures/jours de batch.yaml.
[CmdletBinding()]
param(
    [string]$TaskName = 'AlphaTrade-MarketCapSync',
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
if (-not $WorkspacePath) { $WorkspacePath = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$workspace = (Resolve-Path -LiteralPath $WorkspacePath).Path
$launcher = Join-Path $PSScriptRoot 'market_cap_sync_launcher.ps1'
if (-not (Test-Path -LiteralPath $launcher)) { throw "Launcher introuvable: $launcher" }

if (-not $PythonExePath) { $PythonExePath = Join-Path $workspace '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $PythonExePath)) { throw "Python introuvable: $PythonExePath" }
$python = (Resolve-Path -LiteralPath $PythonExePath).Path
$configPath = Join-Path $workspace 'batch.yaml'
$pyCode = 'import json,sys,yaml; cfg=yaml.safe_load(open(sys.argv[1],encoding=''utf-8'')) or {}; print(json.dumps(cfg.get(''market_cap_sync'') or {}))'
$cfg = ((& $python -c $pyCode $configPath | Out-String).Trim() | ConvertFrom-Json)

$hoursRaw = if ($RunHours) { $RunHours } elseif ($cfg.run_hours) { [string]$cfg.run_hours } else { '11,23' }
$hours = @($hoursRaw -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -match '^\d{1,2}$' } | ForEach-Object { [int]$_ } | Where-Object { $_ -ge 0 -and $_ -le 23 } | Sort-Object -Unique)
if ($hours.Count -eq 0) { throw "run_hours invalide: $hoursRaw" }
$daysRaw = if ($RunDays) { $RunDays } elseif ($cfg.run_days) { [string]$cfg.run_days } else { '' }
$days = @($daysRaw -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -match '^\d$' } | ForEach-Object { [int]$_ } | Where-Object { $_ -ge 0 -and $_ -le 6 } | Sort-Object -Unique)
$effectiveLogFile = if ($LogFile) { $LogFile } elseif ($cfg.log_file) { [string]$cfg.log_file } else { 'log/batch/market_cap_sync.txt' }
if (-not [IO.Path]::IsPathRooted($effectiveLogFile)) { $effectiveLogFile = Join-Path $workspace $effectiveLogFile }

if ($days.Count -gt 0) {
    $dayOfWeek = @($days | ForEach-Object { [DayOfWeek]$_ })
    $triggers = @($hours | ForEach-Object { New-ScheduledTaskTrigger -Weekly -DaysOfWeek $dayOfWeek -At (Get-Date -Hour $_ -Minute 0 -Second 0) })
} else {
    $triggers = @($hours | ForEach-Object { New-ScheduledTaskTrigger -Daily -At (Get-Date -Hour $_ -Minute 0 -Second 0) })
}
$arguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}" -WorkspacePath "{1}" -PythonExePath "{2}" -LogFile "{3}"' -f $launcher, $workspace, $python, $effectiveLogFile
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments -WorkingDirectory $workspace
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 12)
$principal = if ($RunAs -eq 'System') { New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest } else { New-ScheduledTaskPrincipal -UserId $UserId -LogonType Interactive }
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal | Out-Null

$dayNames = @('dimanche', 'lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi')
$dayLabels = @($days | ForEach-Object { $dayNames[$_] })
Write-Host "Task Scheduler installé: $TaskName" -ForegroundColor Green
Write-Host "Heures      : $($hours -join ', ')"
Write-Host "Jours       : $($days -join ',') ($($dayLabels -join ', '))"
Write-Host "RunAs       : $RunAs"
Write-Host "Log statut  : $effectiveLogFile"
