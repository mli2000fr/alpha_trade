# Installe une tâche Forward PIT. Les horaires restent dans batch.yaml.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$BatchName,
    [string]$TaskName,
    [string]$WorkspacePath,
    [string]$PythonExePath,
    [string]$BatchConfigPath,
    [string]$LauncherPath,
    [ValidateSet('Interactive','System')][string]$RunAs='Interactive',
    [string]$UserId=$(if($env:USERDOMAIN){"$($env:USERDOMAIN)\$($env:USERNAME)"}else{$env:USERNAME})
)
$ErrorActionPreference='Stop'; Set-StrictMode -Version Latest
if (-not $WorkspacePath) { $WorkspacePath=Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$workspace=(Resolve-Path -LiteralPath $WorkspacePath).Path
if (-not $PythonExePath) { $PythonExePath=Join-Path $workspace '.venv\Scripts\python.exe' }
$python=(Resolve-Path -LiteralPath $PythonExePath).Path
$configPath=if($BatchConfigPath){$BatchConfigPath}else{Join-Path $workspace 'batch.yaml'}
if(-not [IO.Path]::IsPathRooted($configPath)){$configPath=Join-Path $workspace $configPath}
$pyCode='import json,sys,yaml; c=yaml.safe_load(open(sys.argv[1],encoding=''utf-8'')) or {}; d=c.get(''defaults'') or {}; s=c.get(sys.argv[2]) or {}; print(json.dumps({**d,**s}))'
$cfg=((( & $python -c $pyCode $configPath $BatchName ) | Out-String).Trim() | ConvertFrom-Json)
if (-not $cfg) { throw "Section absente: $BatchName" }
function Get-ConfigValue([object]$Config, [string]$Name, [object]$Default=$null) {
    $property = $Config.PSObject.Properties[$Name]
    if ($null -ne $property) { return $property.Value }
    return $Default
}
if (-not $TaskName) {
    $suffix = ((($BatchName -split '_') | ForEach-Object {
        (Get-Culture).TextInfo.ToTitleCase($_)
    }) -join '')
    $TaskName = 'AlphaTrade-' + $suffix
}
$launcher=if($LauncherPath){$LauncherPath}else{Join-Path $PSScriptRoot 'forward_pit_launcher.ps1'}
if(-not [IO.Path]::IsPathRooted($launcher)){$launcher=Join-Path $workspace $launcher}
$hiddenLauncher=Join-Path $PSScriptRoot 'run_forward_pit_hidden.vbs'
if (-not (Test-Path -LiteralPath $hiddenLauncher)) { throw "Lanceur invisible absent: $hiddenLauncher" }
$powershellExe=(Get-Command 'powershell.exe' -ErrorAction Stop).Source
$wscriptExe=Join-Path $env:WINDIR 'System32\wscript.exe'
if (-not (Test-Path -LiteralPath $wscriptExe)) { throw "Windows Script Host absent: $wscriptExe" }
# Un trigger horaire par minute utile; le launcher applique heure/jour/timezone.
$minutesRaw=[string](Get-ConfigValue $cfg 'run_minutes' '')
$minutes=@($minutesRaw -split ',' | ForEach-Object {$_.Trim()} | Where-Object {$_})
$recoveryMinutesRaw=[string](Get-ConfigValue $cfg 'recovery_run_minutes' '')
$minutes += @($recoveryMinutesRaw -split ',' | ForEach-Object {$_.Trim()} | Where-Object {$_})
if ($minutes.Count -eq 0) { $minutes=@(0) }
$triggers=@()
foreach ($minute in ($minutes | Sort-Object -Unique)) {
    $at=(Get-Date).Date.AddMinutes([int]$minute)
    $triggers += New-ScheduledTaskTrigger -Once -At $at -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 3650)
}
$arguments='//B //Nologo "{0}" "{1}" "{2}" "{3}" "{4}" "{5}"' -f $hiddenLauncher,$powershellExe,$launcher,$BatchName,$workspace,$python
$action=New-ScheduledTaskAction -Execute $wscriptExe -Argument $arguments -WorkingDirectory $workspace
$settings=New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Hours 12)
$principal=if($RunAs -eq 'System'){New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest}else{New-ScheduledTaskPrincipal -UserId $UserId -LogonType Interactive}
$existing=Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if($existing){Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal | Out-Null
Write-Host "Tâche installée: $TaskName" -ForegroundColor Green
Write-Host "Batch: $BatchName ; timezone/configuration: batch.yaml"
