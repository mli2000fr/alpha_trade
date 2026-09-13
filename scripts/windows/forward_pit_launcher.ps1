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
$pyCode = 'import json,sys,yaml; c=yaml.safe_load(open(sys.argv[1],encoding=''utf-8'')) or {}; print(json.dumps(c.get(sys.argv[2]) or {}))'
$cfgText = ((& $python -c $pyCode $configPath $BatchName 2>$null) | Out-String).Trim()
if (-not $cfgText) { throw "Section absente dans batch.yaml: $BatchName" }
$cfg = $cfgText | ConvertFrom-Json
function Get-ConfigValue([object]$Config, [string]$Name, [object]$Default=$null) {
    $property = $Config.PSObject.Properties[$Name]
    if ($null -ne $property) { return $property.Value }
    return $Default
}
$configuredLog = [string](Get-ConfigValue $cfg 'log_file' '')
$effectiveLog = if ($LogFile) { $LogFile } elseif ($configuredLog) { $configuredLog } else { "log/batch/$BatchName.txt" }
if (-not [IO.Path]::IsPathRooted($effectiveLog)) { $effectiveLog = Join-Path $workspace $effectiveLog }
$logDir = Split-Path -Parent $effectiveLog
if (-not (Test-Path -LiteralPath $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
function Write-Status([string]$line) { Add-Content -LiteralPath $effectiveLog -Value $line -Encoding UTF8 }

# Le kill switch est absolu : -Force contourne l'horaire, jamais enabled=false.
$enabled = [bool](Get-ConfigValue $cfg 'enabled' $true)
$status = [string](Get-ConfigValue $cfg 'status' 'ACTIVE')
if (-not $enabled) { Write-Status "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] SKIP $BatchName enabled=false status=$status"; exit 0 }
$isRecovery = $false
if (-not $Force) {
    $tzName = [string](Get-ConfigValue $cfg 'timezone' 'Europe/Paris')
    $tzMap = @{ 'Europe/Paris'='Romance Standard Time'; 'America/New_York'='Eastern Standard Time'; 'UTC'='UTC' }
    $tz = [TimeZoneInfo]::FindSystemTimeZoneById($(if ($tzMap.ContainsKey($tzName)) { $tzMap[$tzName] } else { $tzName }))
    $now = [TimeZoneInfo]::ConvertTime([DateTimeOffset]::UtcNow, $tz)
    $daysRaw = [string](Get-ConfigValue $cfg 'run_days' '')
    $days = @($daysRaw -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($days.Count -gt 0 -and $days -notcontains ([string][int]$now.DayOfWeek)) { exit 0 }
    $hoursRaw = [string](Get-ConfigValue $cfg 'run_hours' '')
    $minutesRaw = [string](Get-ConfigValue $cfg 'run_minutes' '')
    $hours = @($hoursRaw -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    $minutes = @($minutesRaw -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($minutes.Count -eq 0) { $minutes = @(0) }
    $due = $false
    for ($i=0; $i -lt $hours.Count; $i++) {
        $minute = if ($minutes.Count -eq $hours.Count) { [int]$minutes[$i] } else { [int]$minutes[0] }
        if ([int]$hours[$i] -eq $now.Hour -and $minute -eq $now.Minute) { $due = $true; break }
    }
    $recoveryHours = @(([string](Get-ConfigValue $cfg 'recovery_run_hours' '')) -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    $recoveryMinutes = @(([string](Get-ConfigValue $cfg 'recovery_run_minutes' '')) -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    if ($recoveryMinutes.Count -eq 0) { $recoveryMinutes = @(0) }
    for ($i=0; $i -lt $recoveryHours.Count; $i++) {
        $minute = if ($recoveryMinutes.Count -eq $recoveryHours.Count) { [int]$recoveryMinutes[$i] } else { [int]$recoveryMinutes[0] }
        if ([int]$recoveryHours[$i] -eq $now.Hour -and $minute -eq $now.Minute) { $due = $true; $isRecovery = $true; break }
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
if ($isRecovery) {
    $lookback = [double](Get-ConfigValue $cfg 'recovery_success_lookback_hours' 12)
    $gateOutput = @(& $python -u -m service.forward_pit.recovery_gate --batch $BatchName --lookback-hours $lookback 2>&1)
    $gateExit = $LASTEXITCODE
    if ($gateExit -eq 10) { Write-Status "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] SKIP $BatchName recovery-already-completed"; exit 0 }
    if ($gateExit -ne 0) {
        $gateDetail = (($gateOutput | ForEach-Object { $_.ToString() }) -join ' ') -replace '[\r\n]+', ' '
        Write-Status "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] RECOVERY $BatchName gate-unavailable-run-anyway exit=$gateExit detail=$gateDetail"
    } else {
        Write-Status "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] RECOVERY $BatchName primary-missing"
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
    $stdoutTmp = Join-Path ([IO.Path]::GetTempPath()) "alpha_forward_pit_stdout_$PID.txt"
    $stderrTmp = Join-Path ([IO.Path]::GetTempPath()) "alpha_forward_pit_stderr_$PID.txt"
    try {
        # Start-Process garde stderr comme texte brut, sans NativeCommandError PowerShell.
        $batchProcess = Start-Process -FilePath $python -ArgumentList $args `
            -WorkingDirectory $workspace -Wait -PassThru -WindowStyle Hidden `
            -RedirectStandardOutput $stdoutTmp -RedirectStandardError $stderrTmp
        $exitCode = $batchProcess.ExitCode
        $captured = @()
        if (Test-Path -LiteralPath $stdoutTmp) {
            $captured += @(Get-Content -LiteralPath $stdoutTmp -Encoding UTF8)
        }
        if (Test-Path -LiteralPath $stderrTmp) {
            $captured += @(Get-Content -LiteralPath $stderrTmp -Encoding UTF8)
        }
    } finally {
        Remove-Item -LiteralPath $stdoutTmp -Force -ErrorAction SilentlyContinue
        Remove-Item -LiteralPath $stderrTmp -Force -ErrorAction SilentlyContinue
    }
    foreach ($line in $captured) { Write-Status $line.ToString() }
    $duration = (Get-Date) - $started; $state = if ($exitCode -eq 0) { 'OK' } else { 'ERROR' }
    Write-Status "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] FIN $BatchName status=$state exit=$exitCode duration=$($duration.ToString())"
    $tmp = Join-Path ([IO.Path]::GetTempPath()) "alpha_forward_pit_$PID.txt"
    $captured | Select-Object -Last 300 | Set-Content -LiteralPath $tmp -Encoding UTF8
    try {
        $notificationPreviousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            $notificationOutput = @(& $python (Join-Path $workspace 'scripts\send_batch_email.py') --event $BatchName --status $state --exit-code $exitCode --duration $duration.ToString() --log-file $tmp 2>&1)
            $notificationExitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $notificationPreviousErrorActionPreference
        }
        foreach ($line in $notificationOutput) { Write-Status "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] NOTIFY $($line.ToString())" }
        if ($notificationExitCode -ne 0) {
            Write-Status "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] NOTIFY ERROR exit=$notificationExitCode"
        }
    } catch {
        Write-Status "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] NOTIFY ERROR $($_.Exception.Message)"
    } finally {
        Remove-Item -LiteralPath $tmp -Force -ErrorAction SilentlyContinue
    }
    exit $exitCode
} catch {
    $fatalMessage = $_.Exception.Message
    $finished = Get-Date
    $failureDuration = if (Test-Path variable:started) {
        $finished - $started
    } else {
        [TimeSpan]::Zero
    }
    try {
        Write-Status "[$($finished.ToString('yyyy-MM-dd HH:mm:ss'))] FIN $BatchName status=ERROR exit=1 duration=$($failureDuration.ToString()) error=$fatalMessage"
    } catch {
        Write-Error "[$BatchName] $fatalMessage"
    }
    $failureTmp = Join-Path ([IO.Path]::GetTempPath()) "alpha_forward_pit_failure_$PID.txt"
    try {
        @("ERROR: $fatalMessage", $_.ScriptStackTrace) |
            Set-Content -LiteralPath $failureTmp -Encoding UTF8
        $notificationPreviousErrorActionPreference = $ErrorActionPreference
        try {
            $ErrorActionPreference = 'Continue'
            $notificationOutput = @(
                & $python (Join-Path $workspace 'scripts\send_batch_email.py') `
                    --event $BatchName --status ERROR --exit-code 1 `
                    --duration $failureDuration.ToString() --log-file $failureTmp `
                    --failed 1 --error-message $fatalMessage 2>&1
            )
            $notificationExitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $notificationPreviousErrorActionPreference
        }
        foreach ($line in $notificationOutput) {
            Write-Status "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] NOTIFY $($line.ToString())"
        }
    } catch {
        try { Write-Status "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] NOTIFY ERROR $($_.Exception.Message)" } catch {}
    } finally {
        Remove-Item -LiteralPath $failureTmp -Force -ErrorAction SilentlyContinue
    }
    exit 1
} finally {
    if ($locked) { $mutex.ReleaseMutex() }; $mutex.Dispose()
}
