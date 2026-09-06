param(
    [string]$PythonPath = "F:\projets\.venv\Scripts\python.exe"
)

$ErrorActionPreference = "Stop"
$projectRoot = "F:\projets"
$sourcePath = Join-Path $projectRoot "artifacts\models\shared_directional\oracle-amplitude-audit-20260906094826-0802c8\event_metrics.parquet"
$outputRoot = Join-Path $projectRoot "artifacts\models\shared_directional"
$commonArguments = @(
    "-u", "-m", "modelFactory.oracle_options_pilot",
    "--events-path", $sourcePath,
    "--start-date", "2022-03-07",
    "--end-date", "2025-07-11",
    "--dates-per-semester", "1",
    "--minimum-exit-buffer-days", "5",
    "--log-level", "INFO"
)

$runs = @(
    @{ Horizon = 3;  MinDte = 10; TargetDte = 14; MaxDte = 21 },
    @{ Horizon = 5;  MinDte = 14; TargetDte = 21; MaxDte = 28 },
    @{ Horizon = 10; MinDte = 21; TargetDte = 28; MaxDte = 35 },
    @{ Horizon = 20; MinDte = 35; TargetDte = 45; MaxDte = 55 }
)

Set-Location -LiteralPath $projectRoot

foreach ($run in $runs) {
    $outputPath = Join-Path $outputRoot ("oracle-options-dte-20260906-h{0}-0802c8" -f $run.Horizon)
    $reportPath = Join-Path $outputPath "report.json"

    if (Test-Path -LiteralPath $reportPath) {
        Write-Output ("SKIP H{0}: report already present at {1}" -f $run.Horizon, $reportPath)
        continue
    }

    Write-Output ("START H{0}: DTE {1}/{2}/{3}; output={4}" -f $run.Horizon, $run.MinDte, $run.TargetDte, $run.MaxDte, $outputPath)
    $arguments = $commonArguments + @(
        "--output", $outputPath,
        "--horizons", [string]$run.Horizon,
        "--min-dte", [string]$run.MinDte,
        "--target-dte", [string]$run.TargetDte,
        "--max-dte", [string]$run.MaxDte
    )

    & $PythonPath @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "E6-B2 H$($run.Horizon) failed with exit code $LASTEXITCODE"
    }
    Write-Output ("DONE H{0}: {1}" -f $run.Horizon, $reportPath)
}

Write-Output "E6-B2 adaptive-DTE campaign completed."
