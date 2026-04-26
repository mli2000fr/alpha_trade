[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$NssmExePath,
    [string]$ServiceName = 'AlphaTradeProtectionWatcher',
    [string]$DisplayName = 'Alpha Trade Protection Watcher',
    [string]$Description = 'Alpha Trade - service persistant de promotion stop initial vers trailing dynamique.',
    [string]$WorkspacePath = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$PythonExePath,
    [string]$Account,
    [string]$ExecRunId,
    [int]$Limit = 100,
    [double]$ServiceIntervalSeconds = 30.0,
    [double]$IdleIntervalSeconds = 120.0,
    [double]$HeartbeatIntervalSeconds = 300.0,
    [Nullable[int]]$MaxIterations = $null,
    [switch]$StopWhenIdle,
    [int]$MaxConsecutiveFailures = 3,
    [ValidateSet('INFO', 'DEBUG', 'WARNING', 'ERROR')]
    [string]$LogLevel = 'INFO',
    [string]$LogDirectory,
    [switch]$StartAfterInstall
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if (-not (Test-Path -LiteralPath $NssmExePath)) {
    throw "NSSM introuvable: $NssmExePath"
}
$resolvedWorkspace = (Resolve-Path -LiteralPath $WorkspacePath).Path
$launcherPath = Join-Path $PSScriptRoot 'protection_watcher_launcher.ps1'
if (-not (Test-Path -LiteralPath $launcherPath)) {
    throw "Launcher PowerShell introuvable: $launcherPath"
}

$effectiveLogDirectory = if ($LogDirectory) { $LogDirectory } else { Join-Path $resolvedWorkspace 'log\windows_service' }
if (-not (Test-Path -LiteralPath $effectiveLogDirectory)) {
    New-Item -ItemType Directory -Path $effectiveLogDirectory -Force | Out-Null
}
$stdoutPath = Join-Path $effectiveLogDirectory 'protection_watcher_service_stdout.log'
$stderrPath = Join-Path $effectiveLogDirectory 'protection_watcher_service_stderr.log'

$serviceExists = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($serviceExists) {
    & $NssmExePath stop $ServiceName | Out-Null
    & $NssmExePath remove $ServiceName confirm | Out-Null
    Start-Sleep -Seconds 1
}

$launcherArgs = @(
    '-NoProfile',
    '-ExecutionPolicy', 'Bypass',
    '-File', ('"{0}"' -f $launcherPath),
    '-WorkspacePath', ('"{0}"' -f $resolvedWorkspace),
    '-Mode', 'service',
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
    $launcherArgs += @('-PythonExePath', ('"{0}"' -f $PythonExePath))
}
if ($Account) {
    $launcherArgs += @('-Account', $Account)
}
if ($ExecRunId) {
    $launcherArgs += @('-ExecRunId', $ExecRunId)
}
if ($MaxIterations -ne $null) {
    $launcherArgs += @('-MaxIterations', [string]$MaxIterations)
}
if ($StopWhenIdle.IsPresent) {
    $launcherArgs += '-StopWhenIdle'
}
$appParameters = $launcherArgs -join ' '

& $NssmExePath install $ServiceName 'powershell.exe' $appParameters | Out-Null
& $NssmExePath set $ServiceName AppDirectory $resolvedWorkspace | Out-Null
& $NssmExePath set $ServiceName DisplayName $DisplayName | Out-Null
& $NssmExePath set $ServiceName Description $Description | Out-Null
& $NssmExePath set $ServiceName Start SERVICE_AUTO_START | Out-Null
& $NssmExePath set $ServiceName AppStdout $stdoutPath | Out-Null
& $NssmExePath set $ServiceName AppStderr $stderrPath | Out-Null
& $NssmExePath set $ServiceName AppRotateFiles 1 | Out-Null
& $NssmExePath set $ServiceName AppRotateOnline 1 | Out-Null
& $NssmExePath set $ServiceName AppRotateBytes 10485760 | Out-Null

if ($StartAfterInstall.IsPresent) {
    Start-Service -Name $ServiceName
}

Write-Host "Service NSSM installé: $ServiceName" -ForegroundColor Green
Write-Host "Workspace    : $resolvedWorkspace"
Write-Host "Stdout log   : $stdoutPath"
Write-Host "Stderr log   : $stderrPath"
Write-Host "Start auto   : SERVICE_AUTO_START"

