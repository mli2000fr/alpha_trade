# Lance un backtest d'ablation ML-vs-Random (2026-08-17)
# Usage: powershell -File scripts\run_ablation.ps1 -Mode random -Seed 42 -Tag random42
param(
    [ValidateSet("ml", "random")] [string]$Mode = "ml",
    [int]$Seed = 42,
    [string]$Tag = ""
)

$py = "F:\projets\.venv\Scripts\python.exe"
$log = "F:\projets\logs_ablation_${Mode}${Tag}.txt"
$outDir = "F:\projets\artifacts\backtesting\ablation\${Mode}${Tag}"

$args_list = @(
    "-X", "utf8", "-m", "backtesting", "run",
    "--start", "2025-01-01", "--end", "2026-05-31", "--equity", "4000",
    "--output-dir", $outDir,
    "--max-positions", "8",
    "--capital-preset-key", "capital_2001_5000",
    "--use-canonical-costs", "--commission-bps", "1", "--slippage-bps", "2",
    "--margin-interest-rate", "0.075",
    "--allow-fractional-shares",
    "--ml-batch-id", "model-factory-20260811223551-ef2cd0",
    "--engine-mode", "pipeline", "--ml-pit-strategy", "use-persisted",
    "--phase2-mode", "risk_execution", "--phase3-mode", "execution_replay",
    "--phase4-mode", "protection_replay", "--phase5-mode", "watcher_replay",
    "--phase7-mode", "exit_lifecycle_replay",
    "--best-horizon", "20", "--macro-pit-mode", "asof_inclusive",
    "--max-entry-gap-pct", "0.03", "--max-sector-exposure-pct", "0.5",
    "--max-portfolio-dd-pct", "0.15", "--dd-recovery-pct", "0.92",
    "--target-annual-vol", "0.13", "--min-ml-coverage-ratio", "0.9",
    "--cascade-rank-mode", $Mode, "--cascade-rank-seed", "$Seed"
)

Write-Output "==> backtesting run mode=$Mode seed=$Seed"
& $py $args_list *> $log
Write-Output "EXIT=$LASTEXITCODE  (log: $log)"
