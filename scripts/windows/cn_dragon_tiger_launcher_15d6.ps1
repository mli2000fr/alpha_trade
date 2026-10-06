# Lanceur du journal officiel CN, séparé du handler Forward PIT US.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$BatchName,
    [string]$WorkspacePath,
    [string]$PythonExePath,
    [string]$BatchConfigPath,
    [switch]$Force
)
$ErrorActionPreference = 'Stop'
if ($BatchName -notin @('cn_dragon_tiger_after_close','cn_dragon_tiger_before_open')) {
    throw "Batch CN Dragon/Tiger inconnu: $BatchName"
}
if (-not $WorkspacePath) { $WorkspacePath = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$workspace = (Resolve-Path -LiteralPath $WorkspacePath).Path
if (-not $PythonExePath) { $PythonExePath = Join-Path $workspace '.venv\Scripts\python.exe' }
$python = (Resolve-Path -LiteralPath $PythonExePath).Path
$config = if ($BatchConfigPath) { $BatchConfigPath } else { Join-Path $workspace 'batch.yaml' }
if (-not [IO.Path]::IsPathRooted($config)) { $config = Join-Path $workspace $config }
$launcher = Join-Path $PSScriptRoot 'forward_pit_launcher.ps1'
$previousForce = [Environment]::GetEnvironmentVariable('CN_DRAGON_TIGER_FORCE','Process')
try {
    if ($Force) { [Environment]::SetEnvironmentVariable('CN_DRAGON_TIGER_FORCE','1','Process') }
    if (-not $Force) {
        & $python -m service.market.cn_dragon_tiger_schedule_15d6 --batch-name $BatchName --batch-config $config --probe 1>$null 2>$null
        if ($LASTEXITCODE -eq 10) { exit 0 }
        # On preflight error, continue into the common launcher for notification.
    }
    $arguments = @{
        BatchName = $BatchName
        WorkspacePath = $workspace
        RunnerModule = 'service.market.cn_dragon_tiger_schedule_15d6'
        RunnerBatchArgument = '--batch-name'
    }
    $arguments.PythonExePath = $python
    $arguments.BatchConfigPath = $config
    if ($Force) { $arguments.Force = $true }
    & $launcher @arguments
    exit $LASTEXITCODE
} finally {
    [Environment]::SetEnvironmentVariable('CN_DRAGON_TIGER_FORCE',$previousForce,'Process')
}
