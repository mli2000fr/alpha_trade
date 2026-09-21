[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$BatchName,
    [string]$WorkspacePath,
    [string]$PythonExePath,
    [string]$LogFile,
    [string]$EnvFilePath,
    [switch]$Force,
    [switch]$DryRun
)
$ErrorActionPreference='Stop'
if(-not $WorkspacePath){$WorkspacePath=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)}
$launcher=Join-Path $PSScriptRoot 'forward_pit_launcher.ps1'
$parameters=@{
    BatchName=$BatchName
    WorkspacePath=$WorkspacePath
    BatchConfigPath=(Join-Path $WorkspacePath 'batch_cn.yaml')
    RunnerModule='dataIntegrityEngine.cn_provider_ingestion'
    RunnerBatchArgument='--job'
}
if($PythonExePath){$parameters.PythonExePath=$PythonExePath}
if($LogFile){$parameters.LogFile=$LogFile}
if($EnvFilePath){$parameters.EnvFilePath=$EnvFilePath}
if($Force){$parameters.Force=$true}
if($DryRun){$parameters.DryRun=$true}
& $launcher @parameters
exit $LASTEXITCODE
