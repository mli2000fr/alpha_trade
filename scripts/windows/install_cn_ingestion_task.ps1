[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$BatchName,
    [string]$TaskName,
    [string]$WorkspacePath,
    [string]$PythonExePath,
    [ValidateSet('Interactive','System')][string]$RunAs='Interactive',
    [string]$UserId=$(if($env:USERDOMAIN){"$($env:USERDOMAIN)\$($env:USERNAME)"}else{$env:USERNAME})
)
$ErrorActionPreference='Stop'
if(-not $WorkspacePath){$WorkspacePath=Split-Path -Parent (Split-Path -Parent $PSScriptRoot)}
$installer=Join-Path $PSScriptRoot 'install_forward_pit_task.ps1'
$parameters=@{
    BatchName=$BatchName
    WorkspacePath=$WorkspacePath
    BatchConfigPath=(Join-Path $WorkspacePath 'batch_cn.yaml')
    LauncherPath=(Join-Path $PSScriptRoot 'cn_ingestion_launcher.ps1')
    RunAs=$RunAs
    UserId=$UserId
}
if($TaskName){$parameters.TaskName=$TaskName}
if($PythonExePath){$parameters.PythonExePath=$PythonExePath}
& $installer @parameters
exit $LASTEXITCODE
