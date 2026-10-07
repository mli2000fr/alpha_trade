# FR-only wrapper: common scheduling, hidden process, logs and email/Telegram.
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
if ($BatchName -notmatch '^fr_[a-z0-9_]+$') { throw 'FR batch name required' }
if (-not $WorkspacePath) { $WorkspacePath = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$workspace = (Resolve-Path -LiteralPath $WorkspacePath).Path
$config = if ($BatchConfigPath) { $BatchConfigPath } else { Join-Path $workspace 'batch_fr.yaml' }
$arguments = @{
    BatchName = $BatchName
    WorkspacePath = $workspace
    BatchConfigPath = $config
    RunnerModule = 'service.fr.operational_batch_15a'
    RunnerBatchArgument = '--batch'
}
if ($PythonExePath) { $arguments.PythonExePath = $PythonExePath }
if ($Force) { $arguments.Force = $true }
if ($DryRun) { $arguments.DryRun = $true }
& (Join-Path $PSScriptRoot 'forward_pit_launcher.ps1') @arguments
exit $LASTEXITCODE
