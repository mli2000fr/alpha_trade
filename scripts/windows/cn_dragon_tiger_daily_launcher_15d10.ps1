# Lance l'appariement D7 après cutoff avec journal et notifications communes.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$BatchName,
    [string]$WorkspacePath,
    [string]$PythonExePath,
    [string]$BatchConfigPath,
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
if ($BatchName -ne 'cn_dragon_tiger_daily_match') { throw "Batch D7 inconnu: $BatchName" }
if (-not $WorkspacePath) { $WorkspacePath = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$workspace = (Resolve-Path -LiteralPath $WorkspacePath).Path
if (-not $PythonExePath) { $PythonExePath = Join-Path $workspace '.venv\Scripts\python.exe' }
$python = (Resolve-Path -LiteralPath $PythonExePath).Path
$config = if ($BatchConfigPath) { $BatchConfigPath } else { Join-Path $workspace 'batch.yaml' }
if (-not [IO.Path]::IsPathRooted($config)) { $config = Join-Path $workspace $config }
$previousEncoding = [Environment]::GetEnvironmentVariable('PYTHONIOENCODING', 'Process')
try {
    [Environment]::SetEnvironmentVariable('PYTHONIOENCODING', 'utf-8', 'Process')
    if (-not $Force) {
        & $python -m service.market.cn_dragon_tiger_daily_15d10 --batch $BatchName --batch-config $config --probe 1>$null 2>$null
        if ($LASTEXITCODE -eq 10) { exit 0 }
    }
    $arguments = @{
        BatchName = $BatchName
        WorkspacePath = $workspace
        PythonExePath = $python
        BatchConfigPath = $config
        RunnerModule = 'service.market.cn_dragon_tiger_daily_15d10'
        RunnerBatchArgument = '--batch'
    }
    if ($Force) { $arguments.Force = $true }
    & (Join-Path $PSScriptRoot 'forward_pit_launcher.ps1') @arguments
    exit $LASTEXITCODE
} finally {
    [Environment]::SetEnvironmentVariable('PYTHONIOENCODING', $previousEncoding, 'Process')
}
