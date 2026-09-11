# Collecte les capitalisations Yahoo puis Finnhub pour l'univers actions.
# Usage manuel :
#   powershell -ExecutionPolicy Bypass -File .\scripts\windows\market_cap_sync_launcher.ps1
#   powershell -ExecutionPolicy Bypass -File .\scripts\windows\market_cap_sync_launcher.ps1 -IgnoreRunDays
#     (-IgnoreRunDays force le traitement un jour hors run_days : rattrapage manuel)
[CmdletBinding()]
param(
    [string]$WorkspacePath,
    [string]$PythonExePath,
    [string]$LogFile,
    [string]$EnvFilePath,
    [switch]$IgnoreRunDays
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if (-not $WorkspacePath) {
    $WorkspacePath = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}
$resolvedWorkspace = (Resolve-Path -LiteralPath $WorkspacePath).Path

function Resolve-AlphaTradePythonExe {
    param([string]$Workspace, [string]$RequestedPythonExePath)
    if ($RequestedPythonExePath) {
        if (-not (Test-Path -LiteralPath $RequestedPythonExePath)) {
            throw "Python introuvable: $RequestedPythonExePath"
        }
        return (Resolve-Path -LiteralPath $RequestedPythonExePath).Path
    }
    foreach ($candidate in @(
        (Join-Path $Workspace '.venv\Scripts\python.exe'),
        (Join-Path $Workspace 'venv\Scripts\python.exe'),
        (Join-Path $Workspace '.python\Scripts\python.exe')
    )) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand) { return $pythonCommand.Source }
    throw 'Aucun interpréteur Python exploitable trouvé.'
}

function Import-AlphaTradeEnvFile {
    param([string]$Path)
    if (-not $Path) { return }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) { continue }
        $separatorIndex = $trimmed.IndexOf('=')
        if ($separatorIndex -lt 1) { continue }
        $key = $trimmed.Substring(0, $separatorIndex).Trim()
        $value = $trimmed.Substring($separatorIndex + 1).Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        if ($key) { Set-Item -Path ("Env:{0}" -f $key) -Value $value }
    }
}

function Read-MarketCapSyncConfig {
    param([string]$Workspace, [string]$PythonExe)
    $configPath = Join-Path $Workspace 'config.yaml'
    if (-not (Test-Path -LiteralPath $configPath)) { return $null }
    $pyCode = 'import json,sys,yaml; cfg=yaml.safe_load(open(sys.argv[1],encoding=''utf-8'')) or {}; print(json.dumps(cfg.get(''market_cap_sync'') or {}))'
    try {
        $jsonOut = (& $PythonExe -c $pyCode $configPath 2>$null | Out-String).Trim()
        if ($jsonOut) { return ($jsonOut | ConvertFrom-Json) }
    } catch { return $null }
    return $null
}

$effectiveLogFile = if ($LogFile) { $LogFile } else { 'log/batch/market_cap_sync.txt' }
if (-not [IO.Path]::IsPathRooted($effectiveLogFile)) {
    $effectiveLogFile = Join-Path $resolvedWorkspace $effectiveLogFile
}
$logDir = Split-Path -Parent $effectiveLogFile
if ($logDir -and -not (Test-Path -LiteralPath $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}
function Write-StatusLine { param([string]$Line) Add-Content -LiteralPath $effectiveLogFile -Value $Line -Encoding UTF8 }

function Send-MarketCapNotification {
    param(
        [string]$PythonExe,
        [string]$Status,
        [int]$ExitCode,
        [string]$Duration,
        [object[]]$CapturedOutput = @(),
        [string[]]$Warnings = @()
    )
    try {
        $notificationTmp = Join-Path ([IO.Path]::GetTempPath()) ("alpha_market_cap_log_{0}.txt" -f $PID)
        if ($CapturedOutput.Count -gt 0) {
            (@($CapturedOutput) | Select-Object -Last 300) -join "`n" | Set-Content -LiteralPath $notificationTmp -Encoding UTF8
        } else {
            Set-Content -LiteralPath $notificationTmp -Value '(aucune sortie capturée)' -Encoding UTF8
        }
        $notificationArgs = @(
            '--event', 'market_cap_sync',
            '--status', $Status,
            '--exit-code', $ExitCode,
            '--duration', $Duration,
            '--log-file', $notificationTmp
        )
        foreach ($warning in $Warnings) { $notificationArgs += @('--warning', $warning) }
        & $PythonExe (Join-Path $resolvedWorkspace 'scripts\send_batch_email.py') @notificationArgs 2>&1 | Out-Null
        Remove-Item -LiteralPath $notificationTmp -Force -ErrorAction SilentlyContinue
    } catch {
        Write-StatusLine ("[{0}] NOTE notifications email/Telegram non envoyées: {1}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $_.Exception.Message)
    }
}

$started = Get-Date
Write-StatusLine ("[{0}] DÉBUT DE TRAITEMENT market_cap_sync pid={1} - le batch est lancé" -f $started.ToString('yyyy-MM-dd HH:mm:ss'), $PID)

try {
    $resolvedPython = Resolve-AlphaTradePythonExe -Workspace $resolvedWorkspace -RequestedPythonExePath $PythonExePath
} catch {
    Write-StatusLine ("[{0}] FIN TRAITEMENT ERROR market_cap_sync - {1}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $_.Exception.Message)
    exit 1
}

$cfg = Read-MarketCapSyncConfig -Workspace $resolvedWorkspace -PythonExe $resolvedPython
if (-not $LogFile -and $cfg -and $cfg.log_file) {
    $effectiveLogFile = [string]$cfg.log_file
    if (-not [IO.Path]::IsPathRooted($effectiveLogFile)) { $effectiveLogFile = Join-Path $resolvedWorkspace $effectiveLogFile }
    $logDir = Split-Path -Parent $effectiveLogFile
    if ($logDir -and -not (Test-Path -LiteralPath $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }
}

$runDaysValue = if ($cfg -and $cfg.run_days) { [string]$cfg.run_days } else { '' }
$runDays = @($runDaysValue -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' })
if ($IgnoreRunDays) {
    Write-StatusLine ("[{0}] FORCE market_cap_sync - garde run_days='{1}' ignorée (jour={2})" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $runDaysValue, [string][int](Get-Date).DayOfWeek)
} elseif ($runDays.Count -gt 0) {
    $dow = [string][int](Get-Date).DayOfWeek
    if ($runDays -notcontains $dow) {
        Write-StatusLine ("[{0}] SKIP market_cap_sync - jour={1} absent de run_days='{2}'" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $dow, $runDaysValue)
        exit 0
    }
}

# Le planificateur utilise déjà MultipleInstances=IgnoreNew. Ce mutex couvre
# aussi les lancements manuels concurrents.
$mutex = New-Object System.Threading.Mutex($false, 'Local\AlphaTradeMarketCapSync')
$mutexAcquired = $false
try {
    try { $mutexAcquired = $mutex.WaitOne(0) } catch [System.Threading.AbandonedMutexException] { $mutexAcquired = $true }
    if (-not $mutexAcquired) {
        Write-StatusLine ("[{0}] SKIP market_cap_sync - une exécution est déjà en cours" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'))
        exit 0
    }

    $resolvedEnvFile = $EnvFilePath
    if (-not $resolvedEnvFile) {
        foreach ($candidate in @((Join-Path $PSScriptRoot 'market_cap_sync.env'), (Join-Path $resolvedWorkspace '.env'))) {
            if (Test-Path -LiteralPath $candidate) { $resolvedEnvFile = $candidate; break }
        }
    }
    if ($resolvedEnvFile) { Import-AlphaTradeEnvFile -Path $resolvedEnvFile }

    if (-not $cfg) { throw 'section market_cap_sync absente ou illisible dans config.yaml' }
    $symbolsFileValue = [string]$cfg.symbols_file
    if (-not $symbolsFileValue) { throw 'market_cap_sync.symbols_file est obligatoire' }
    $symbolsFilePath = $symbolsFileValue
    if (-not [IO.Path]::IsPathRooted($symbolsFilePath)) { $symbolsFilePath = Join-Path $resolvedWorkspace $symbolsFilePath }
    if (-not (Test-Path -LiteralPath $symbolsFilePath)) { throw "univers introuvable: $symbolsFilePath" }
    # Le chemin configuré est transmis à Python (relatif au workspace, séparateurs POSIX) :
    # config/univers/<fichier>.txt reste résolu par nom, tout autre dossier sous config/ par chemin.
    $configRoot = (Resolve-Path -LiteralPath (Join-Path $resolvedWorkspace 'config')).Path
    $configPrefix = $configRoot.TrimEnd([char]'\') + '\'
    $resolvedSymbolsFile = (Resolve-Path -LiteralPath $symbolsFilePath).Path
    if (-not $resolvedSymbolsFile.StartsWith($configPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'symbols_file doit être situé sous config/'
    }
    if (-not $resolvedSymbolsFile.EndsWith('.txt', [StringComparison]::OrdinalIgnoreCase)) {
        throw "symbols_file doit désigner un fichier .txt: $resolvedSymbolsFile"
    }
    $relativeSymbolsFile = $resolvedSymbolsFile.Substring($configPrefix.Length).Replace('\', '/')
    $symbolSource = 'universe-file:config/{0}' -f $relativeSymbolsFile

    $providersValue = if ($cfg.providers) { [string]$cfg.providers } else { 'yahoo_finance,finnhub' }
    $providers = @($providersValue -split ',' | ForEach-Object { $_.Trim().ToLowerInvariant() } | Where-Object { $_ -ne '' })
    $allowedProviders = @('yahoo_finance', 'finnhub')
    if ($providers.Count -eq 0 -or @($providers | Where-Object { $allowedProviders -notcontains $_ }).Count -gt 0) {
        throw "providers invalides: $providersValue"
    }

    $env:PYTHONIOENCODING = 'utf-8'
    [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
    $OutputEncoding = [System.Text.Encoding]::UTF8
    $overallExitCode = 0
    $allCaptured = @()
    $batchWarnings = @()
    Push-Location $resolvedWorkspace
    try {
        foreach ($provider in $providers) {
            Write-StatusLine ("[{0}] START provider={1} univers={2}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $provider, $symbolSource)
            $commandArgs = @('-u', '-m', 'modelFactory.fundamental_features', '--provider', $provider, '--symbol-source', $symbolSource)
            $captured = @(& $resolvedPython @commandArgs 2>&1)
            $providerExitCode = $LASTEXITCODE
            $allCaptured += $captured
            $summaryLine = @($captured | ForEach-Object { $_.ToString() } | Where-Object { $_ -like '::alpha_trade_run_summary::*' } | Select-Object -Last 1)
            $stored = $null
            $failed = $null
            if ($summaryLine.Count -gt 0) {
                try {
                    $summary = ($summaryLine[-1] -replace '^::alpha_trade_run_summary::', '') | ConvertFrom-Json
                    $stored = [int]$summary.stored
                    $failed = [int]$summary.failed
                } catch { $providerExitCode = 1 }
            } else { $providerExitCode = 1 }
            if ($providerExitCode -ne 0 -or $null -eq $stored -or $stored -eq 0) {
                $overallExitCode = 1
                Write-StatusLine ("[{0}] ERROR provider={1} exit={2} stored={3} failed={4}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $provider, $providerExitCode, $stored, $failed)
            } elseif ($failed -gt 0) {
                $batchWarnings += "provider=$provider collecte partielle: stored=$stored failed=$failed"
                Write-StatusLine ("[{0}] WARNING provider={1} stored={2} failed={3}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $provider, $stored, $failed)
            } else {
                Write-StatusLine ("[{0}] OK provider={1} stored={2} failed=0" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $provider, $stored)
            }
        }
    } finally { Pop-Location }

    $finished = Get-Date
    $duration = $finished - $started
    $durationText = '{0}h{1:D2}m{2:D2}s' -f [int]$duration.TotalHours, $duration.Minutes, $duration.Seconds
    $statusText = if ($overallExitCode -eq 0) { 'OK' } else { 'ERROR' }
    Write-StatusLine ("[{0}] FIN TRAITEMENT {1} market_cap_sync exit={2} durée={3} - détail: log/fundamental_features.log" -f $finished.ToString('yyyy-MM-dd HH:mm:ss'), $statusText, $overallExitCode, $durationText)

    Send-MarketCapNotification -PythonExe $resolvedPython -Status $statusText -ExitCode $overallExitCode -Duration $durationText -CapturedOutput $allCaptured -Warnings $batchWarnings
    exit $overallExitCode
} catch {
    $duration = (Get-Date) - $started
    $durationText = '{0}h{1:D2}m{2:D2}s' -f [int]$duration.TotalHours, $duration.Minutes, $duration.Seconds
    $fatalError = ($_.Exception.Message -replace '[\r\n]+', ' ')
    Write-StatusLine ("[{0}] FIN TRAITEMENT ERROR market_cap_sync exit=1 durée={1} err={2}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $durationText, $fatalError)
    Send-MarketCapNotification -PythonExe $resolvedPython -Status 'ERROR' -ExitCode 1 -Duration $durationText -CapturedOutput @($fatalError)
    exit 1
} finally {
    if ($mutexAcquired) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
