# Installe la tâche Windows du canary P0j. Les horaires viennent du YAML.
[CmdletBinding()]
param(
    [string]$TaskName = 'AlphaTrade-OracleCanary',
    [string]$WorkspacePath,
    [string]$PythonExePath,
    [string]$ConfigPath,
    [ValidateSet('Interactive', 'System')][string]$RunAs = 'Interactive',
    [string]$UserId = $(if ($env:USERDOMAIN) { "$($env:USERDOMAIN)\$($env:USERNAME)" } else { $env:USERNAME })
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not $WorkspacePath) { $WorkspacePath = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$workspace = (Resolve-Path -LiteralPath $WorkspacePath).Path
if (-not $PythonExePath) { $PythonExePath = Join-Path $workspace '.venv\Scripts\python.exe' }
if (-not $ConfigPath) { $ConfigPath = Join-Path $workspace 'config\oracle_canary.yaml' }
if (-not (Test-Path -LiteralPath $PythonExePath)) { throw "Python introuvable: $PythonExePath" }
if (-not (Test-Path -LiteralPath $ConfigPath)) { throw "Configuration introuvable: $ConfigPath" }
$pyCode = 'import json,sys,yaml; print(json.dumps(yaml.safe_load(open(sys.argv[1],encoding=''utf-8'')) or {}))'
$cfg = ((& $PythonExePath -c $pyCode $ConfigPath | Out-String).Trim() | ConvertFrom-Json)
$hours = @(([string]$cfg.run_hours -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -match '^\d{1,2}$' } | ForEach-Object { [int]$_ } | Where-Object { $_ -ge 0 -and $_ -le 23 } | Sort-Object -Unique)
if ($hours.Count -eq 0) { $hours = @(23) }
$days = @(([string]$cfg.run_days -split ',') | ForEach-Object { $_.Trim() } | Where-Object { $_ -match '^\d$' } | ForEach-Object { [int]$_ } | Where-Object { $_ -ge 0 -and $_ -le 6 } | Sort-Object -Unique)
if ($days.Count -gt 0) {
    $dayValues = @($days | ForEach-Object { [DayOfWeek]$_ })
    $triggers = @($hours | ForEach-Object { New-ScheduledTaskTrigger -Weekly -DaysOfWeek $dayValues -At (Get-Date -Hour $_ -Minute 0 -Second 0) })
} else {
    $triggers = @($hours | ForEach-Object { New-ScheduledTaskTrigger -Daily -At (Get-Date -Hour $_ -Minute 0 -Second 0) })
}
$launcher = Join-Path $PSScriptRoot 'oracle_canary_launcher.ps1'
$arguments = '-NoProfile -ExecutionPolicy Bypass -File "{0}" -WorkspacePath "{1}" -PythonExePath "{2}" -ConfigPath "{3}"' -f $launcher,$workspace,$PythonExePath,$ConfigPath
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments -WorkingDirectory $workspace
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 12)
$principal = if ($RunAs -eq 'System') { New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest } else { New-ScheduledTaskPrincipal -UserId $UserId -LogonType Interactive }
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) { Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false }
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal | Out-Null
Write-Host "Tâche installée: $TaskName" -ForegroundColor Green
Write-Host "Heures: $($hours -join ',') — jours: $($days -join ',') — RunAs: $RunAs"

