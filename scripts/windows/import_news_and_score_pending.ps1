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

    [Parameter()]
    [ValidateSet('alpaca', 'finnhub', 'eodhd')]
    [string]$NewsProvider = 'eodhd',

    [Parameter()]
    [ValidateSet('provider_default', 'strict', 'scored')]
    [string]$TickerRelevanceMode = 'provider_default',

    [Parameter()]
    [string]$Symbols = '',

    [Parameter()]
    [ValidateSet('stock_scores', 'stock_scores_history', 'stock_scores_all', 'candidates', 'stock_bars_daily')]
    [string]$SymbolSource = 'stock_scores',

    [Parameter()]
    [int]$MaxSymbols = 0,

    [Parameter()]
    [double]$MinRelevanceScore = 0.0,

    [Parameter()]
    [switch]$EnableContextualScoring,

    [Parameter()]
    [double]$ContextualMinRelevance = 0.0,

    [Parameter()]
    [int]$ContextualMaxPairs = 5000,

    [Parameter()]
    [switch]$RelevanceBackfillDryRun,

    [Parameter()]
    [switch]$RelevanceBackfillRescoreAll,

    [Parameter()]
    [switch]$RelevanceBackfillRescoreContextual,

    [Parameter()]
    [double]$RelevanceBackfillPurgeBelow = 0.0,

    [Parameter()]
    [int]$RelevanceBackfillBatchSize = 500,

    [Parameter()]
    [double]$RelevanceBackfillContextualMinRelevance = 0.0,

    [Parameter()]
    [int]$RelevanceBackfillContextualMaxPairs = 0,

    [switch]$SkipImport,

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

$NormalizedImportSymbols = @()
if (-not [string]::IsNullOrWhiteSpace($Symbols)) {
    $NormalizedImportSymbols = @(
        $Symbols -split ',' |
        ForEach-Object { $_.Trim().ToUpperInvariant() } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        Select-Object -Unique
    )
}
$NormalizedImportSymbolsCsv = if ($NormalizedImportSymbols.Count -gt 0) {
    $NormalizedImportSymbols -join ','
}
else {
    ''
}

$summary = [ordered]@{
    mode = if ($SkipImport) {
        'score_pending_history_and_relevance_backfill'
    }
    else {
        'import_news_score_pending_history_and_relevance_backfill'
    }
    start_date = $StartDate
    end_date = $EndDate
    project_root = $ProjectRoot
    python_exe = $PythonExe
    dry_run = [bool]$DryRun
    import_completed = $false
    scoring_runs_executed = 0
    initial_pending = $null
    final_pending = $null
    initial_pending_global = $null
    final_pending_global = $null
    max_iterations = $MaxIterations
    max_stagnant_iterations = $MaxStagnantIterations
    history_backfill_enabled = -not [bool]$SkipHistoryBackfill
    history_backfill_batch_days = $HistoryBackfillBatchDays
    history_backfill_completed = $false
    relevance_backfill_enabled = $true
    relevance_backfill_batch_size = $RelevanceBackfillBatchSize
    relevance_backfill_completed = $false
    news_provider = $NewsProvider
    ticker_relevance_mode = $TickerRelevanceMode
    import_symbols = if ($NormalizedImportSymbols.Count -gt 0) { @($NormalizedImportSymbols) } else { @() }
    import_symbol_source = $SymbolSource
    import_max_symbols = $MaxSymbols
    min_relevance_score = $MinRelevanceScore
    enable_contextual_scoring = [bool]$EnableContextualScoring
    contextual_min_relevance = $ContextualMinRelevance
    contextual_max_pairs = $ContextualMaxPairs
    relevance_backfill_dry_run = [bool]$RelevanceBackfillDryRun
    relevance_backfill_rescore_all = [bool]$RelevanceBackfillRescoreAll
    relevance_backfill_rescore_contextual = [bool]$RelevanceBackfillRescoreContextual
    relevance_backfill_purge_below = $RelevanceBackfillPurgeBelow
    relevance_backfill_contextual_min_relevance = $RelevanceBackfillContextualMinRelevance
    relevance_backfill_contextual_max_pairs = $RelevanceBackfillContextualMaxPairs
    pending_scope_start_date = $StartDate
    pending_scope_end_date = $EndDate
    pending_scope_ingestion_source = $NewsProvider
    pending_scope_symbols = if ($NormalizedImportSymbols.Count -gt 0) { @($NormalizedImportSymbols) } else { @() }
    skip_import = [bool]$SkipImport
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
    param(
        [string]$PendingStartDate = '',
        [string]$PendingEndDate = '',
        [string]$IngestionSource = '',
        [string]$SymbolsCsv = ''
    )

    if ($DryRun) {
        return 0
    }

    $pendingStartDateLiteral = if ([string]::IsNullOrWhiteSpace($PendingStartDate)) {
        'None'
    }
    else {
        "'" + $PendingStartDate.Replace("'", "\\'") + "'"
    }
    $pendingEndDateLiteral = if ([string]::IsNullOrWhiteSpace($PendingEndDate)) {
        'None'
    }
    else {
        "'" + $PendingEndDate.Replace("'", "\\'") + "'"
    }
    $ingestionSourceLiteral = if ([string]::IsNullOrWhiteSpace($IngestionSource)) {
        'None'
    }
    else {
        "'" + $IngestionSource.Replace("'", "\\'") + "'"
    }
    $normalizedSymbols = @()
    if (-not [string]::IsNullOrWhiteSpace($SymbolsCsv)) {
        $normalizedSymbols = @(
            $SymbolsCsv -split ',' |
            ForEach-Object { $_.Trim().ToUpperInvariant() } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            Select-Object -Unique
        )
    }
    $symbolsLiteral = if ($normalizedSymbols.Count -eq 0) {
        'None'
    }
    else {
        '[' + (($normalizedSymbols | ForEach-Object { "'" + $_.Replace("'", "\\'") + "'" }) -join ', ') + ']'
    }

    $pythonCode = @"
from datetime import date

from event_sentiment.db_io import EventSentimentRepository

start_date = date.fromisoformat($pendingStartDateLiteral) if $pendingStartDateLiteral != None else None
end_date = date.fromisoformat($pendingEndDateLiteral) if $pendingEndDateLiteral != None else None
ingestion_source = $ingestionSourceLiteral
symbols = $symbolsLiteral
repository = EventSentimentRepository()
print(repository.count_pending_articles(
    start_date=start_date,
    end_date=end_date,
    ingestion_source=ingestion_source,
    symbols=symbols,
))
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

function Get-RunWindowUtcBounds {
    return @{
        StartUtc = ("{0}T00:00:00Z" -f $StartDate)
        EndUtc = ("{0}T23:59:59Z" -f $EndDate)
    }
}

function Resolve-ScopedSymbols {
    param(
        [string]$ExplicitSymbolsCsv = '',
        [string]$SelectedSymbolSource = 'stock_scores'
    )

    $explicitSymbols = @()
    if (-not [string]::IsNullOrWhiteSpace($ExplicitSymbolsCsv)) {
        $explicitSymbols = @(
            $ExplicitSymbolsCsv -split ',' |
            ForEach-Object { $_.Trim().ToUpperInvariant() } |
            Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
            Select-Object -Unique
        )
    }
    if ($explicitSymbols.Count -gt 0) {
        return $explicitSymbols
    }
    if ($SelectedSymbolSource -eq 'stock_bars_daily' -or $DryRun) {
        return @()
    }

    $pythonCode = switch ($SelectedSymbolSource) {
        'candidates' {
@"
from event_sentiment.db_io import EventSentimentRepository

for symbol in EventSentimentRepository().load_candidate_symbols():
    print(str(symbol).strip().upper())
"@
        }
        'stock_scores_history' {
@"
from event_sentiment.importe_news import get_all_symbols_from_stock_scores_history

for symbol in get_all_symbols_from_stock_scores_history():
    print(str(symbol).strip().upper())
"@
        }
        'stock_scores_all' {
@"
from event_sentiment.importe_news import get_all_symbols_from_stock_scores_all

for symbol in get_all_symbols_from_stock_scores_all():
    print(str(symbol).strip().upper())
"@
        }
        default {
@"
from event_sentiment.importe_news import get_all_symbols_from_stock_scores

for symbol in get_all_symbols_from_stock_scores(candidates_only=False):
    print(str(symbol).strip().upper())
"@
        }
    }

    $output = & $PythonExe -u -c $pythonCode 2>&1
    $exitCode = if ($null -ne $LASTEXITCODE) { [int]$LASTEXITCODE } else { 0 }
    if ($exitCode -ne 0) {
        $details = ($output | ForEach-Object { $_.ToString() }) -join [Environment]::NewLine
        throw ("Impossible de résoudre le scope de symboles (source={0}, exit={1}).`n{2}" -f $SelectedSymbolSource, $exitCode, $details)
    }
    return @(
        $output |
        ForEach-Object { $_.ToString().Trim().ToUpperInvariant() } |
        Where-Object { -not [string]::IsNullOrWhiteSpace($_) } |
        Select-Object -Unique
    )
}

Push-Location $ProjectRoot
try {
    $ScopedSymbols = @(Resolve-ScopedSymbols -ExplicitSymbolsCsv $NormalizedImportSymbolsCsv -SelectedSymbolSource $SymbolSource)
    $ScopedSymbolsCsv = if ($ScopedSymbols.Count -gt 0) { $ScopedSymbols -join ',' } else { '' }
    $summary.pending_scope_symbols = if ($ScopedSymbols.Count -gt 0) { @($ScopedSymbols) } else { @() }

    $importNewsArguments = @(
        '-u',
        (Join-Path $ProjectRoot 'event_sentiment\importe_news.py'),
        '--start-date',
        $StartDate,
        '--end-date',
        $EndDate,
        '--news-provider',
        $NewsProvider
    )
    if ($NormalizedImportSymbols.Count -gt 0) {
        $importNewsArguments += @('--symbols', $NormalizedImportSymbolsCsv)
    }
    elseif ($SymbolSource -ne 'stock_scores') {
        $importNewsArguments += @('--symbol-source', $SymbolSource)
    }
    if ($MaxSymbols -gt 0) {
        $importNewsArguments += @('--max-symbols', ([string]$MaxSymbols))
    }
    if ($TickerRelevanceMode -ne 'provider_default') {
        $importNewsArguments += @('--ticker-relevance-mode', $TickerRelevanceMode)
    }
    if ($TickerRelevanceMode -eq 'scored' -and $MinRelevanceScore -gt 0) {
        $importNewsArguments += @('--min-relevance-score', ([string]$MinRelevanceScore))
    }

    if (-not $SkipImport) {
        Invoke-PythonStep -Label 'Import news brutes historiques' -Arguments @($importNewsArguments)
        $summary.import_completed = $true
    }
    else {
        Write-Host 'Import news brutes historiques ignoré (SkipImport actif).'
    }

    $pendingCount = Get-PendingArticleCount -PendingStartDate $StartDate -PendingEndDate $EndDate -IngestionSource $NewsProvider -SymbolsCsv $ScopedSymbolsCsv
    $summary.initial_pending = $pendingCount
    $summary.initial_pending_global = Get-PendingArticleCount
    Write-Host ("Articles pending après import (scope {0} → {1}, provider={2}) : {3}" -f $StartDate, $EndDate, $NewsProvider, $pendingCount)
    if ($summary.initial_pending_global -ne $summary.initial_pending) {
        Write-Warning (
            "Backlog pending global détecté hors scope 7.bis (global={0}, scope={1}). Le wrapper va traiter uniquement le scope demandé." -f
            $summary.initial_pending_global, $summary.initial_pending
        )
    }

    $stagnantIterations = 0
    $runWindow = Get-RunWindowUtcBounds
    while ($pendingCount -gt 0) {
        if ($summary.scoring_runs_executed -ge $MaxIterations) {
            throw ("Boucle arrêtée : MaxIterations={0} atteint alors qu'il reste {1} article(s) pending." -f $MaxIterations, $pendingCount)
        }

        $runIndex = [int]$summary.scoring_runs_executed + 1
        Write-Host ("=== Scoring auto #{0} | pending avant run : {1} ===" -f $runIndex, $pendingCount)
        $scoringArguments = @(
            '-u',
            '-m',
            'event_sentiment',
            '--skip-ingestion',
            '--news-provider',
            $NewsProvider,
            '--start-utc',
            $runWindow.StartUtc,
            '--end-utc',
            $runWindow.EndUtc
        )
        if ($ScopedSymbols.Count -gt 0) {
            $scoringArguments += @('--symbols', $ScopedSymbolsCsv)
        }
        if ($TickerRelevanceMode -ne 'provider_default') {
            $scoringArguments += @('--ticker-relevance-mode', $TickerRelevanceMode)
        }
        if ($TickerRelevanceMode -eq 'scored' -and $MinRelevanceScore -gt 0) {
            $scoringArguments += @('--min-relevance-score', ([string]$MinRelevanceScore))
        }
        if ($EnableContextualScoring) {
            $scoringArguments += '--enable-contextual-scoring'
            if ($ContextualMinRelevance -gt 0) {
                $scoringArguments += @('--contextual-min-relevance', ([string]$ContextualMinRelevance))
            }
            if ($ContextualMaxPairs -gt 0) {
                $scoringArguments += @('--contextual-max-pairs', ([string]$ContextualMaxPairs))
            }
        }
        Invoke-PythonStep -Label ("Sentiment pipeline auto #{0}" -f $runIndex) -Arguments @($scoringArguments)
        $summary.scoring_runs_executed = $runIndex

        $remaining = Get-PendingArticleCount -PendingStartDate $StartDate -PendingEndDate $EndDate -IngestionSource $NewsProvider -SymbolsCsv $ScopedSymbolsCsv
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
    $summary.final_pending_global = Get-PendingArticleCount
    Write-Host 'Import + scoring auto terminés : plus aucun article pending dans le scope demandé.'
    if ($summary.final_pending_global -gt 0) {
        Write-Warning (
            "Il reste {0} article(s) pending hors scope ({1} → {2}, provider={3})." -f
            $summary.final_pending_global, $StartDate, $EndDate, $NewsProvider
        )
    }

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

    $relevanceBackfillArguments = @(
        '-u',
        '-m',
        'event_sentiment.relevance_backfill',
        '--start-date',
        $StartDate,
        '--end-date',
        $EndDate,
        '--batch-size',
        [string]$RelevanceBackfillBatchSize
    )
    if ($RelevanceBackfillDryRun) {
        $relevanceBackfillArguments += '--dry-run'
    }
    if ($RelevanceBackfillRescoreAll) {
        $relevanceBackfillArguments += '--rescore-all'
    }
    if ($RelevanceBackfillPurgeBelow -gt 0) {
        $relevanceBackfillArguments += @('--purge-below', ([string]$RelevanceBackfillPurgeBelow))
    }
    if ($ScopedSymbols.Count -gt 0) {
        $relevanceBackfillArguments += @('--symbols', $ScopedSymbolsCsv)
    }
    if ($RelevanceBackfillRescoreContextual) {
        $relevanceBackfillArguments += '--rescore-contextual'
        if ($RelevanceBackfillContextualMinRelevance -gt 0) {
            $relevanceBackfillArguments += @('--contextual-min-relevance', ([string]$RelevanceBackfillContextualMinRelevance))
        }
        if ($RelevanceBackfillContextualMaxPairs -gt 0) {
            $relevanceBackfillArguments += @('--contextual-max-pairs', ([string]$RelevanceBackfillContextualMaxPairs))
        }
    }
    Invoke-PythonStep -Label 'Relevance backfill auto' -Arguments @($relevanceBackfillArguments)
    $summary.relevance_backfill_completed = $true
    Write-Host 'Relevance backfill auto terminé.'

    $summary.status = 'completed'
    Write-RunSummary -Payload $summary
}
catch {
    $summary.status = 'failed'
    try {
        $summary.final_pending = Get-PendingArticleCount -PendingStartDate $StartDate -PendingEndDate $EndDate -IngestionSource $NewsProvider -SymbolsCsv $ScopedSymbolsCsv
        $summary.final_pending_global = Get-PendingArticleCount
    }
    catch {
        if ($null -eq $summary.final_pending) {
            $summary.final_pending = -1
        }
        if ($null -eq $summary.final_pending_global) {
            $summary.final_pending_global = -1
        }
    }
    $summary.error = $_.Exception.Message
    Write-RunSummary -Payload $summary
    throw
}
finally {
    Pop-Location
}
