# analyst_snapshot_launcher.ps1
#
# Collecte prospective Yahoo analyst (RESEARCH ONLY) :
#   python -u scripts/collect_yahoo_analyst_snapshots.py --universe analyst_research --write-db --resume
# et journalise une ligne de statut (START / OK / ERROR) dans
#   log/batch/analyst_snapshots.txt
# (chemin piloté par config.yaml → analyst_snapshot_collection.log_file).
#
# Point d'entrée utilisé par la tâche planifiée Windows
# « AlphaTrade-AnalystSnapshot » (install_analyst_snapshot_task.ps1),
# qui déclenche ce launcher automatiquement aux heures de
# config.yaml → analyst_snapshot_collection.run_hours ("18" = 18h America/New_York,
# après clôture US ; "3,14" = 3h et 14h).
#
# Usage manuel :
#   powershell -ExecutionPolicy Bypass -File .\scripts\windows\analyst_snapshot_launcher.ps1
[CmdletBinding()]
param(
    [string]$WorkspacePath,
    [string]$PythonExePath,
    [string]$LogFile,
    [string]$EnvFilePath
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

function Read-AnalystSnapshotConfig {
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
    $pyCode = 'import json,sys,yaml; cfg=yaml.safe_load(open(sys.argv[1],encoding=''utf-8'')) or {}; print(json.dumps(cfg.get(''analyst_snapshot_collection'') or {}))'
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

function Import-AlphaTradeEnvFile {
    param([string]$Path)

    if (-not $Path) {
        return
    }

    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) {
            continue
        }
        $separatorIndex = $trimmed.IndexOf('=')
        if ($separatorIndex -lt 1) {
            continue
        }
        $key = $trimmed.Substring(0, $separatorIndex).Trim()
        $value = $trimmed.Substring($separatorIndex + 1).Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        if ($key) {
            Set-Item -Path ("Env:{0}" -f $key) -Value $value
        }
    }
}

$resolvedWorkspace = (Resolve-Path -LiteralPath $WorkspacePath).Path

# ── Fichier de statut : déterminé AU PLUS TÔT (avant de résoudre Python)
#    pour garantir l'écriture du « début de traitement ». ──
$effectiveLogFile = $LogFile
if (-not $effectiveLogFile) {
    $effectiveLogFile = 'log/batch/analyst_snapshots.txt'
}
if (-not [IO.Path]::IsPathRooted($effectiveLogFile)) {
    $effectiveLogFile = Join-Path $resolvedWorkspace $effectiveLogFile
}
$logDir = Split-Path -Parent $effectiveLogFile
if ($logDir -and -not (Test-Path -LiteralPath $logDir)) {
    New-Item -ItemType Directory -Path $logDir -Force | Out-Null
}

function Write-StatusLine {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Line
    )
    Add-Content -LiteralPath $effectiveLogFile -Value $Line -Encoding UTF8
}

# ── DÉBUT DE TRAITEMENT : écrit immédiatement (sait que le batch tourne) ──
$started = Get-Date
Write-StatusLine ("[{0}] DÉBUT DE TRAITEMENT analyst_snapshot_collect pid={1} — le batch est lancé" -f $started.ToString('yyyy-MM-dd HH:mm:ss'), $PID)

# ── Interpréteur Python (indispensable) ──
try {
    $resolvedPython = Resolve-AlphaTradePythonExe -Workspace $resolvedWorkspace -RequestedPythonExePath $PythonExePath
} catch {
    Write-StatusLine ("[{0}] FIN TRAITEMENT ERROR  analyst_snapshot_collect — Python indisponible : {1}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), ($_.Exception.Message -replace '[\r\n]+', ' '))
    exit 1
}

# ── Chargement optionnel d'un .env (LOGIN_DB / PASSWORD_DB, etc.) ──
# Nécessaire quand la tâche planifiée ne reprend pas l'environnement du shell.
$resolvedEnvFile = $EnvFilePath
if (-not $resolvedEnvFile) {
    foreach ($candidate in @(
        (Join-Path $PSScriptRoot 'analyst_snapshot.env'),
        (Join-Path $resolvedWorkspace '.env')
    )) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            $resolvedEnvFile = $candidate
            break
        }
    }
}
if ($resolvedEnvFile) {
    Import-AlphaTradeEnvFile -Path $resolvedEnvFile
}

# ── Configuration depuis config.yaml (log_file, symbols_file) ──
$cfg = Read-AnalystSnapshotConfig -Workspace $resolvedWorkspace -PythonExe $resolvedPython
if (-not $LogFile -and $cfg -and ($cfg.PSObject.Properties.Name -contains 'log_file') -and $cfg.log_file) {
    $cfgLogFile = [string]$cfg.log_file
    if (-not [IO.Path]::IsPathRooted($cfgLogFile)) {
        $cfgLogFile = Join-Path $resolvedWorkspace $cfgLogFile
    }
    if ($cfgLogFile -ne $effectiveLogFile) {
        $effectiveLogFile = $cfgLogFile
        $cfgLogDir = Split-Path -Parent $effectiveLogFile
        if ($cfgLogDir -and -not (Test-Path -LiteralPath $cfgLogDir)) {
            New-Item -ItemType Directory -Path $cfgLogDir -Force | Out-Null
        }
        Write-StatusLine ("[{0}] NOTE   log_file = config.yaml → {1}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $effectiveLogFile)
    }
}

# ── Univers : symbols_file (config.yaml) — warning si absent OU introuvable ──
#    Le collecteur lit lui-même analyst_snapshot_collection.symbols_file
#    (fichier 2255, même fichier qu'earnings_calendar_sync) ; sinon repli
#    univers active-tradable (~13 600). On avertit ici pour que le warning
#    remonte dans le log de statut + email + Telegram.
$batchWarnings = @()
$symbolsFileValue = ''
if ($cfg -and ($cfg.PSObject.Properties.Name -contains 'symbols_file') -and $cfg.symbols_file) {
    $symbolsFileValue = [string]$cfg.symbols_file
}
if (-not $symbolsFileValue) {
    $warnMsg = "analyst_snapshot_collection.symbols_file non renseigné (config.yaml) — repli univers active-tradable (~13 600)"
    $batchWarnings += $warnMsg
    Write-StatusLine ("[{0}] WARNING univers — {1}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $warnMsg)
} else {
    $symbolsFilePath = $symbolsFileValue
    if (-not [IO.Path]::IsPathRooted($symbolsFilePath)) {
        $symbolsFilePath = Join-Path $resolvedWorkspace $symbolsFilePath
    }
    if (Test-Path -LiteralPath $symbolsFilePath) {
        Write-StatusLine ("[{0}] NOTE   univers = symbols_file → {1}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $symbolsFilePath)
    } else {
        $warnMsg = "analyst_snapshot_collection.symbols_file introuvable : $symbolsFilePath — repli univers active-tradable (~13 600)"
        $batchWarnings += $warnMsg
        Write-StatusLine ("[{0}] WARNING univers — {1}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $warnMsg)
    }
}

# Commande de collecte (mêmes arguments que la doc config.yaml).
$collectScriptPath = Join-Path $resolvedWorkspace 'scripts\collect_yahoo_analyst_snapshots.py'
$commandArgs = @(
    '-u',
    $collectScriptPath,
    '--universe', 'analyst_research',
    '--write-db',
    '--resume'
)

# P-fix (2026-08-31) : `$captured` initialisé AVANT le try — sous Set-StrictMode, référencer
# une variable jamais assignée lève « Impossible d'extraire la variable $captured » et bloquait
# l'envoi de l'email de fin (best-effort). Garantit que le bloc email marche même si le process
# python n'a jamais pu être lancé (throw → catch).
$captured = $null
$exitCode = 0
$errorMsg = ''
try {
    Push-Location $resolvedWorkspace
    try {
        # ── Encodage UTF-8 : le collecteur écrit en UTF-8 (sys.stdout.reconfigure) et
        #    PS 5.1 décoderait sinon la sortie en CP850 (OEM) → mojibake (ex. ├®) dans l'email. ──
        $env:PYTHONIOENCODING = 'utf-8'
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        $OutputEncoding = [System.Text.Encoding]::UTF8
        $captured = @(& $resolvedPython @commandArgs 2>&1)
        $exitCode = $LASTEXITCODE
        # P-fix (2026-08-31) : capturer l'ERREUR RÉELLE. Les stderr python arrivent sous forme
        # d'ErrorRecord multi-lignes dont .ToString() du premier ne donne que
        # « Traceback (most recent call last): ». On concatène tout et on prend la DERNIÈRE
        # ligne non vide = « ExceptionType: message » (ex. FileNotFoundError: ...).
        $stderrRecords = @($captured | Where-Object { $_ -is [System.Management.Automation.ErrorRecord] } | ForEach-Object { $_.ToString() })
        if ($stderrRecords.Count -gt 0) {
            $stderrText = $stderrRecords -join "`n"
            $stderrLines = @($stderrText -split "`r?`n" | Where-Object { $_.Trim() })
            $errorMsg = (($stderrLines[-1]) -replace '[\r\n]+', ' ').Trim()
        }
    } finally {
        Pop-Location
    }
} catch {
    $exitCode = 1
    if (-not $errorMsg) {
        $errorMsg = ($_.Exception.Message -replace '[\r\n]+', ' ').Trim()
    }
}
if ($errorMsg.Length -gt 240) { $errorMsg = $errorMsg.Substring(0, 240) }

$finished = Get-Date
$stamp = $finished.ToString('yyyy-MM-dd HH:mm:ss')
$dur = $finished - $started
$durStr = '{0}h{1:D2}m{2:D2}s' -f [int]$dur.TotalHours, $dur.Minutes, $dur.Seconds

if ($exitCode -eq 0) {
    Write-StatusLine ("[{0}] FIN TRAITEMENT OK     analyst_snapshot_collect exit=0 durée={1} — log/batch/analyst_snapshots.log" -f $stamp, $durStr)
} else {
    $err = if ($errorMsg) { " err=$errorMsg" } else { '' }
    Write-StatusLine ("[{0}] FIN TRAITEMENT ERROR  analyst_snapshot_collect exit={1} durée={2}{3} — log/batch/analyst_snapshots.log" -f $stamp, $exitCode, $durStr, $err)
}

# ── Email de fin de batch (statut + logs de CE run) via email_notifier ──
# Best-effort : un échec d'envoi ne fait jamais échouer le batch.
try {
    $emailTmp = Join-Path ([IO.Path]::GetTempPath()) ("alpha_batch_log_{0}.txt" -f $PID)
    if ($captured) {
        (@($captured) | Select-Object -Last 300) -join "`n" | Set-Content -LiteralPath $emailTmp -Encoding UTF8
    } else {
        Set-Content -LiteralPath $emailTmp -Value '(aucune sortie)' -Encoding UTF8
    }
    $emailStatus = if ($exitCode -eq 0) { 'OK' } else { 'ERROR' }
    $emailArgs = @(
        '--event', 'analyst_snapshot_collect',
        '--status', $emailStatus,
        '--exit-code', $exitCode,
        '--duration', $durStr,
        '--log-file', $emailTmp
    )
    foreach ($warningLine in $batchWarnings) {
        $emailArgs += @('--warning', $warningLine)
    }
    & $resolvedPython (Join-Path $resolvedWorkspace 'scripts\send_batch_email.py') @emailArgs 2>&1 | Out-Null
    Remove-Item -LiteralPath $emailTmp -Force -ErrorAction SilentlyContinue
} catch {
    Write-StatusLine ("[{0}] NOTE   email de fin non envoyé (best-effort) : {1}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), ($_.Exception.Message -replace '[\r\n]+', ' '))
}

exit $exitCode
