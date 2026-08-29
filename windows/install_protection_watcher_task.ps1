[CmdletBinding()]
param(
    [string]$TaskName = 'AlphaTrade-ProtectionWatcher',
    [string]$WorkspacePath = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$PythonExePath,
    [string]$EnvFilePath,
    [string]$SecretStorePath,
    [string]$Account,
    [string]$ExecRunId,
    [ValidateSet('once', 'service')]
    [string]$Mode = 'once',
    [int]$Limit = 100,
    [int]$FrequencyMinutes = 5,
    [double]$ServiceIntervalSeconds = 30.0,
    [double]$IdleIntervalSeconds = 120.0,
    [double]$HeartbeatIntervalSeconds = 300.0,
    [Nullable[int]]$MaxIterations = $null,
    [switch]$StopWhenIdle,
    [int]$MaxConsecutiveFailures = 3,
    [ValidateSet('Interactive', 'System')]
    [string]$RunAs = 'Interactive',
    [string]$UserId = $(if ($env:USERDOMAIN) { "$($env:USERDOMAIN)\$($env:USERNAME)" } else { $env:USERNAME }),
    [ValidateSet('INFO', 'DEBUG', 'WARNING', 'ERROR')]
    [string]$LogLevel = 'INFO',
    [string]$LogDirectory
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$resolvedWorkspace = (Resolve-Path -LiteralPath $WorkspacePath).Path
$launcherPath = Join-Path $PSScriptRoot 'protection_watcher_launcher.ps1'
if (-not (Test-Path -LiteralPath $launcherPath)) {
    throw "Launcher PowerShell introuvable: $launcherPath"
}

$effectiveLogDirectory = if ($LogDirectory) { $LogDirectory } else { Join-Path $resolvedWorkspace 'log\windows_scheduler' }
if (-not (Test-Path -LiteralPath $effectiveLogDirectory)) {
    New-Item -ItemType Directory -Path $effectiveLogDirectory -Force | Out-Null
}
$stdoutPath = Join-Path $effectiveLogDirectory 'protection_watcher_task_stdout.log'
$stderrPath = Join-Path $effectiveLogDirectory 'protection_watcher_task_stderr.log'

$argumentList = @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', ('"{0}"' -f $launcherPath),
    '-WorkspacePath', ('"{0}"' -f $resolvedWorkspace),
    '-Mode', $Mode,
    '-Limit', [string]$Limit,
    '-ServiceIntervalSeconds', [string]$ServiceIntervalSeconds,
    '-IdleIntervalSeconds', [string]$IdleIntervalSeconds,
    '-HeartbeatIntervalSeconds', [string]$HeartbeatIntervalSeconds,
    '-MaxConsecutiveFailures', [string]$MaxConsecutiveFailures,
    '-LogLevel', $LogLevel,
    '-StdoutPath', ('"{0}"' -f $stdoutPath),
    '-StderrPath', ('"{0}"' -f $stderrPath)
)
if ($PythonExePath) {
    $argumentList += @('-PythonExePath', ('"{0}"' -f $PythonExePath))
}
if ($EnvFilePath) {
    $argumentList += @('-EnvFilePath', ('"{0}"' -f $EnvFilePath))
}
if ($SecretStorePath) {
    $argumentList += @('-SecretStorePath', ('"{0}"' -f $SecretStorePath))
}
if ($Account) {
    $argumentList += @('-Account', $Account)
}
if ($ExecRunId) {
    $argumentList += @('-ExecRunId', $ExecRunId)
}
if ($MaxIterations -ne $null) {
    $argumentList += @('-MaxIterations', [string]$MaxIterations)
}
if ($StopWhenIdle.IsPresent) {
    $argumentList += '-StopWhenIdle'
}
$actionArguments = $argumentList -join ' '

$startAt = (Get-Date).AddMinutes(1)
$trigger = New-ScheduledTaskTrigger -Once -At $startAt -RepetitionInterval (New-TimeSpan -Minutes $FrequencyMinutes) -RepetitionDuration (New-TimeSpan -Days 3650)
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument $actionArguments -WorkingDirectory $resolvedWorkspace
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -MultipleInstances IgnoreNew -StartWhenAvailable
$principal = if ($RunAs -eq 'System') {
    New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
}
else {
    New-ScheduledTaskPrincipal -UserId $UserId -LogonType Interactive -RunLevel Highest
}

$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal | Out-Null

Write-Host "Task Scheduler installé: $TaskName" -ForegroundColor Green
Write-Host "Workspace           : $resolvedWorkspace"
Write-Host "Mode                : $Mode"
Write-Host "Fréquence (minutes) : $FrequencyMinutes"
Write-Host "Stdout log          : $stdoutPath"
Write-Host "Stderr log          : $stderrPath"


