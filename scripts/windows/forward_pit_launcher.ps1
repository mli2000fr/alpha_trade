# Lance un batch Forward PIT configuré exclusivement dans batch.yaml.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$BatchName,
    [string]$WorkspacePath,
    [string]$PythonExePath,
    [string]$LogFile,
    [string]$EnvFilePath,
    [switch]$Force,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not $WorkspacePath) { $WorkspacePath = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$workspace = (Resolve-Path -LiteralPath $WorkspacePath).Path
if (-not $PythonExePath) { $PythonExePath = Join-Path $workspace '.venv\Scripts\python.exe' }
$python = (Resolve-Path -LiteralPath $PythonExePath).Path
$configPath = Join-Path $workspace 'batch.yaml'
$pyCode = 'import json,sys,yaml; c=yaml.safe_load(open(sys.argv[1],encoding="utf-8")) or {}; print(json.dumps(c.get(sys.argv[2]) or {}))'
$cfgText = ((& $python -c $pyCode $configPath $BatchName 2>$null) | Out-String).Trim()
if (-not $cfgText) { throw "Section absente dans batch.yaml: $BatchName" }
$cfg = $cfgText | ConvertFrom-Json
$effectiveLog = if ($LogFile) { $LogFile } elseif ($cfg.log_file) { [string]$cfg.log_file } else { "log/batch/$BatchName.txt" }
if (-not [IO.Path]::IsPathRooted($effectiveLog)) { $effectiveLog = Join-Path $workspace $effectiveLog }
$logDir = Split-Path -Parent $effectiveLog
if (-not (Test-Path -LiteralPath $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
function Write-Status([string]$line) { Add-Content -LiteralPath $effectiveLog -Value $line -Encoding UTF8 }

# Le kill switch est absolu : -Force contourne l'horaire, jamais enabled=false.
if (-not $cfg.enabled) { Write-Status "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] SKIP $BatchName enabled=false status=$($cfg.status)"; exit 0 }
if (-not $Force) {
    $tzName = if ($cfg.timezone) { [string]$cfg.timezone } else { 'Europe/Paris' }
    $tzMap = @{ 'Europe/Paris'='Romance Standard Time'; 'America/New_York'='Eastern Standard Time'; 'UTC'='UTC' }
    $tz = [TimeZoneInfo]::FindSystemTimeZoneById($(if ($tzMap.ContainsKey($tzName)) { $tzMap[$tzName] } else { $tzName }))
    $now = [TimeZoneInfo]::ConvertTime([DateTimeOffset]::UtcNow, $tz)
    $days = @(([string]$cfg.run_days) -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($days.Count -gt 0 -and $days -notcontains ([string][int]$now.DayOfWeek)) { exit 0 }
    $hours = @(([string]$cfg.run_hours) -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    $minutes = @(([string]$cfg.run_minutes) -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($minutes.Count -eq 0) { $minutes = @(0) }
    $due = $false
    for ($i=0; $i -lt $hours.Count; $i++) {
        $minute = if ($minutes.Count -eq $hours.Count) { [int]$minutes[$i] } else { [int]$minutes[0] }
        if ([int]$hours[$i] -eq $now.Hour -and $minute -eq $now.Minute) { $due = $true; break }
    }
    if (-not $due) { exit 0 }
}

if (-not $EnvFilePath) {
    foreach ($candidate in @((Join-Path $PSScriptRoot 'forward_pit.env'), (Join-Path $workspace '.env'))) {
        if (Test-Path -LiteralPath $candidate) { $EnvFilePath = $candidate; break }
    }
}
if ($EnvFilePath) {
    foreach ($line in Get-Content -LiteralPath $EnvFilePath -Encoding UTF8) {
        $value = $line.Trim(); if (-not $value -or $value.StartsWith('#')) { continue }
        $pos = $value.IndexOf('='); if ($pos -lt 1) { continue }
        $name = $value.Substring(0,$pos).Trim(); $data = $value.Substring($pos+1).Trim().Trim('"').Trim("'")
        if ($name) { Set-Item -Path "Env:$name" -Value $data }
    }
}
$mutexName = 'Local\AlphaTradeForwardPIT' + ($BatchName -replace '[^A-Za-z0-9]','')
$mutex = New-Object System.Threading.Mutex($false, $mutexName); $locked = $false
try {
    try { $locked = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { Write-Status "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] SKIP $BatchName already-running"; exit 0 }
    $started = Get-Date; Write-Status "[$($started.ToString('yyyy-MM-dd HH:mm:ss'))] START $BatchName pid=$PID"
    $args = @('-u','-m','service.forward_pit.batch','--batch',$BatchName,'--batch-config',$configPath)
    if ($DryRun) { $args += '--dry-run' }
    Push-Location $workspace
    try { $captured = @(& $python @args 2>&1); $exitCode = $LASTEXITCODE } finally { Pop-Location }
    foreach ($line in $captured) { Write-Status $line.ToString() }
    $duration = (Get-Date) - $started; $state = if ($exitCode -eq 0) { 'OK' } else { 'ERROR' }
    Write-Status "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] FIN $BatchName status=$state exit=$exitCode duration=$($duration.ToString())"
    $tmp = Join-Path ([IO.Path]::GetTempPath()) "alpha_forward_pit_$PID.txt"
    $captured | Select-Object -Last 300 | Set-Content -LiteralPath $tmp -Encoding UTF8
    & $python (Join-Path $workspace 'scripts\send_batch_email.py') --event $BatchName --status $state --exit-code $exitCode --duration $duration.ToString() --log-file $tmp 2>&1 | Out-Null
    Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    exit $exitCode
} finally {
    if ($locked) { $mutex.ReleaseMutex() }; $mutex.Dispose()
}
