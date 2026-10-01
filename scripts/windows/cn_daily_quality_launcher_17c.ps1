# Contrôle CN 17-C : préflight calendrier, puis lanceur commun (logs/mail/Telegram).
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$BatchName,
    [string]$WorkspacePath,
    [string]$PythonExePath,
    [string]$BatchConfigPath,
    [switch]$Force,
    [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
if ($BatchName -ne 'cn_daily_quality_17c') { throw "Batch qualité CN inconnu: $BatchName" }
if (-not $WorkspacePath) { $WorkspacePath = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$workspace = (Resolve-Path -LiteralPath $WorkspacePath).Path
if (-not $PythonExePath) { $PythonExePath = Join-Path $workspace '.venv\Scripts\python.exe' }
$python = (Resolve-Path -LiteralPath $PythonExePath).Path
$config = if ($BatchConfigPath) { $BatchConfigPath } else { Join-Path $workspace 'batch_cn.yaml' }
if (-not [IO.Path]::IsPathRooted($config)) { $config = Join-Path $workspace $config }
$previousEncoding = [Environment]::GetEnvironmentVariable('PYTHONIOENCODING', 'Process')
try {
    [Environment]::SetEnvironmentVariable('PYTHONIOENCODING', 'utf-8', 'Process')
    if (-not $Force) {
        & $python -m service.market.cn_daily_quality_17c --batch $BatchName --batch-config $config --probe 1>$null 2>$null
        if ($LASTEXITCODE -eq 10) { exit 0 }
        # Une panne du préflight passe au lanceur commun pour produire une alerte.
    }
    $arguments = @{
        BatchName = $BatchName
        WorkspacePath = $workspace
        PythonExePath = $python
        BatchConfigPath = $config
        RunnerModule = 'service.market.cn_daily_quality_17c'
        RunnerBatchArgument = '--batch'
    }
    if ($Force) { $arguments.Force = $true }
    if ($DryRun) { $arguments.DryRun = $true }
    & (Join-Path $PSScriptRoot 'forward_pit_launcher.ps1') @arguments
    exit $LASTEXITCODE
} finally {
    [Environment]::SetEnvironmentVariable('PYTHONIOENCODING', $previousEncoding, 'Process')
}
