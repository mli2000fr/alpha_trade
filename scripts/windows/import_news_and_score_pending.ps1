[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d{4}-\d{2}-\d{2}$')]
    [string]$StartDate,

    [Parameter()]
    [ValidatePattern('^\d{4}-\d{2}-\d{2}$')]
    [string]$EndDate = (Get-Date).ToString('yyyy-MM-dd'),

    [Parameter()]
    [string]$PythonExe = '',

    [Parameter()]
    [string]$ProjectRoot = '',

    [Parameter()]
    [int]$MaxIterations = 250,

    [Parameter()]
    [int]$MaxStagnantIterations = 2,

    [Parameter()]
    [int]$SleepSecondsBetweenRuns = 1,

    [Parameter()]
    [int]$HistoryBackfillBatchDays = 63,

    [switch]$SkipHistoryBackfill,

    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($ProjectRoot)) {
    $ProjectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
}
if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = (Get-Command python -ErrorAction Stop).Source
}

$summary = [ordered]@{
    mode = 'import_news_score_pending_and_history_backfill'
    start_date = $StartDate
    end_date = $EndDate
    project_root = $ProjectRoot
    python_exe = $PythonExe
    dry_run = [bool]$DryRun
    import_completed = $false
    scoring_runs_executed = 0
    initial_pending = $null
    final_pending = $null
    max_iterations = $MaxIterations
    max_stagnant_iterations = $MaxStagnantIterations
    history_backfill_enabled = -not [bool]$SkipHistoryBackfill
    history_backfill_batch_days = $HistoryBackfillBatchDays
    history_backfill_completed = $false
    status = 'running'
}

function Write-RunSummary {
    param([hashtable]$Payload)
    Write-Output ("::alpha_trade_run_summary::" + (($Payload | ConvertTo-Json -Depth 6 -Compress)))
}

function Format-CommandDisplay {
    param(
        [string]$Exe,
        [string[]]$Arguments
    )

    $parts = @($Exe) + $Arguments
    return ($parts | ForEach-Object {
        if ($_ -match '[\s"]') {
            '"' + ($_ -replace '"', '\\"') + '"'
        }
        else {
            $_
        }
    }) -join ' '
}

function Invoke-PythonStep {
    param(
        [string]$Label,
        [string[]]$Arguments
    )

    Write-Host ("=== {0} ===" -f $Label)
    Write-Host ("Command: {0}" -f (Format-CommandDisplay -Exe $PythonExe -Arguments $Arguments))
    if ($DryRun) {
        return
    }

    & $PythonExe @Arguments
    $exitCode = if ($null -ne $LASTEXITCODE) { [int]$LASTEXITCODE } else { 0 }
    if ($exitCode -ne 0) {
        throw ("Commande en échec pour '{0}' (exit={1})." -f $Label, $exitCode)
    }
}

function Get-PendingArticleCount {
    if ($DryRun) {
        return 0
    }

    $pythonCode = @"
from database.connection import get_sqlalchemy_engine
from sqlalchemy import text

engine = get_sqlalchemy_engine()
query = text(
    """
    SELECT COUNT(*)
    FROM news_raw nr
    LEFT JOIN news_sentiment ns ON ns.article_id = nr.article_id
    WHERE ns.article_id IS NULL
    """
)
with engine.connect() as conn:
    print(int(conn.execute(query).scalar_one() or 0))
"@

    $output = & $PythonExe -u -c $pythonCode 2>&1
    $exitCode = if ($null -ne $LASTEXITCODE) { [int]$LASTEXITCODE } else { 0 }
    if ($exitCode -ne 0) {
        $details = ($output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
        throw ("Impossible de lire le nombre d'articles pending (exit={0}).`n{1}" -f $exitCode, $details)
    }

    $lastLine = $output | ForEach-Object { $_.ToString().Trim() } | Where-Object { $_ -ne '' } | Select-Object -Last 1
    if ($null -eq $lastLine -or $lastLine -notmatch '^\d+$') {
        $details = ($output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
        throw ("Sortie pending inattendue.`n{0}" -f $details)
    }
    return [int]$lastLine
}

Push-Location $ProjectRoot
try {
    Invoke-PythonStep -Label 'Import news brutes historiques' -Arguments @(
        '-u',
        (Join-Path $ProjectRoot 'event_sentiment\importe_news.py'),
        '--start-date',
        $StartDate,
        '--end-date',
        $EndDate
    )
    $summary.import_completed = $true

    $pendingCount = Get-PendingArticleCount
    $summary.initial_pending = $pendingCount
    Write-Host ("Articles pending après import : {0}" -f $pendingCount)

    $stagnantIterations = 0
    while ($pendingCount -gt 0) {
        if ($summary.scoring_runs_executed -ge $MaxIterations) {
            throw ("Boucle arrêtée : MaxIterations={0} atteint alors qu'il reste {1} article(s) pending." -f $MaxIterations, $pendingCount)
        }

        $runIndex = [int]$summary.scoring_runs_executed + 1
        Write-Host ("=== Scoring auto #{0} | pending avant run : {1} ===" -f $runIndex, $pendingCount)
        Invoke-PythonStep -Label ("Sentiment pipeline auto #{0}" -f $runIndex) -Arguments @('-u', '-m', 'event_sentiment')
        $summary.scoring_runs_executed = $runIndex

        $remaining = Get-PendingArticleCount
        Write-Host ("Articles pending après scoring #{0} : {1}" -f $runIndex, $remaining)

        if ($remaining -lt $pendingCount) {
            $stagnantIterations = 0
        }
        else {
            $stagnantIterations += 1
            Write-Warning (
                "Le nombre d'articles pending n'a pas diminué après le run #{0} (avant={1}, après={2}, stagnation={3}/{4})." -f
                $runIndex, $pendingCount, $remaining, $stagnantIterations, $MaxStagnantIterations
            )
            if ($remaining -gt 0 -and $stagnantIterations -ge $MaxStagnantIterations) {
                throw (
                    "Boucle arrêtée : pending non décroissant après {0} run(s) consécutif(s). Reste {1} article(s) pending." -f
                    $stagnantIterations, $remaining
                )
            }
        }

        $pendingCount = $remaining
        if ($pendingCount -gt 0 -and $SleepSecondsBetweenRuns -gt 0) {
            Start-Sleep -Seconds $SleepSecondsBetweenRuns
        }
    }

    $summary.final_pending = $pendingCount
    Write-Host 'Import + scoring auto terminés : plus aucun article pending.'

    if (-not $SkipHistoryBackfill) {
        Invoke-PythonStep -Label 'History backfill auto' -Arguments @(
            '-u',
            '-m',
            'event_sentiment.history_backfill',
            '--start-date',
            $StartDate,
            '--end-date',
            $EndDate,
            '--batch-days',
            [string]$HistoryBackfillBatchDays
        )
        $summary.history_backfill_completed = $true
        Write-Host 'History backfill auto terminé.'
    }
    else {
        Write-Host 'History backfill auto ignoré (SkipHistoryBackfill actif).'
    }

    $summary.status = 'completed'
    Write-RunSummary -Payload $summary
}
catch {
    $summary.status = 'failed'
    try {
        $summary.final_pending = Get-PendingArticleCount
    }
    catch {
        if ($null -eq $summary.final_pending) {
            $summary.final_pending = -1
        }
    }
    $summary.error = $_.Exception.Message
    Write-RunSummary -Payload $summary
    throw
}
finally {
    Pop-Location
}
