# Installe une tâche Forward PIT. Les horaires restent dans batch.yaml.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$BatchName,
    [string]$TaskName,
    [string]$WorkspacePath,
    [string]$PythonExePath,
    [ValidateSet('Interactive','System')][string]$RunAs='Interactive',
    [string]$UserId=$(if($env:USERDOMAIN){"$($env:USERDOMAIN)\$($env:USERNAME)"}else{$env:USERNAME})
)
$ErrorActionPreference='Stop'; Set-StrictMode -Version Latest
if (-not $WorkspacePath) { $WorkspacePath=Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$workspace=(Resolve-Path -LiteralPath $WorkspacePath).Path
if (-not $PythonExePath) { $PythonExePath=Join-Path $workspace '.venv\Scripts\python.exe' }
$python=(Resolve-Path -LiteralPath $PythonExePath).Path
$configPath=Join-Path $workspace 'batch.yaml'
$pyCode='import json,sys,yaml; c=yaml.safe_load(open(sys.argv[1],encoding="utf-8")) or {}; print(json.dumps(c.get(sys.argv[2]) or {}))'
$cfg=((( & $python -c $pyCode $configPath $BatchName ) | Out-String).Trim() | ConvertFrom-Json)
if (-not $cfg) { throw "Section absente: $BatchName" }
if (-not $TaskName) { $TaskName='AlphaTrade-' + (($BatchName -split '_') | ForEach-Object { (Get-Culture).TextInfo.ToTitleCase($_) }) -join '' }
$launcher=Join-Path $PSScriptRoot 'forward_pit_launcher.ps1'
# Un trigger horaire par minute utile; le launcher applique heure/jour/timezone.
$minutes=@(([string]$cfg.run_minutes) -split ',' | ForEach-Object {$_.Trim()} | Where-Object {$_})
if ($minutes.Count -eq 0) { $minutes=@(0) }
$triggers=@()
foreach ($minute in ($minutes | Sort-Object -Unique)) {
    $at=(Get-Date).Date.AddMinutes([int]$minute)
    $triggers += New-ScheduledTaskTrigger -Once -At $at -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)
}
$arguments='-NoProfile -ExecutionPolicy Bypass -File "{0}" -BatchName "{1}" -WorkspacePath "{2}" -PythonExePath "{3}"' -f $launcher,$BatchName,$workspace,$python
$action=New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $arguments -WorkingDirectory $workspace
$settings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 12)
$principal=if($RunAs -eq 'System'){New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest}else{New-ScheduledTaskPrincipal -UserId $UserId -LogonType Interactive}
$existing=Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if($existing){Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal | Out-Null
Write-Host "Tâche installée: $TaskName" -ForegroundColor Green
Write-Host "Batch: $BatchName ; timezone/configuration: batch.yaml"

