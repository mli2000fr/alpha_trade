# Sauvegarde CN isolée via le lanceur commun de logs et notifications.
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
if ($BatchName -ne 'cn_db_backup') { throw "Batch sauvegarde CN inconnu: $BatchName" }
if (-not $WorkspacePath) { $WorkspacePath = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$workspace = (Resolve-Path -LiteralPath $WorkspacePath).Path
$config = if ($BatchConfigPath) { $BatchConfigPath } else { Join-Path $workspace 'batch_cn.yaml' }
if (-not [IO.Path]::IsPathRooted($config)) { $config = Join-Path $workspace $config }
$arguments = @{
    BatchName = $BatchName
    WorkspacePath = $workspace
    BatchConfigPath = $config
    RunnerModule = 'service.market.cn_db_backup_17b'
    RunnerBatchArgument = '--batch'
}
if ($PythonExePath) { $arguments.PythonExePath = $PythonExePath }
if ($Force) { $arguments.Force = $true }
if ($DryRun) { $arguments.DryRun = $true }
& (Join-Path $PSScriptRoot 'forward_pit_launcher.ps1') @arguments
exit $LASTEXITCODE
