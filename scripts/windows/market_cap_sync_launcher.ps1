# Launcher de compatibilité pour market_cap_sync.
# La configuration batch.yaml est lue par le launcher Forward PIT commun.
# L'orchestration métier est centralisée dans service.forward_pit.batch afin
# que SEC -> Yahoo -> Finnhub, les compteurs SQL et les notifications restent
# identiques entre tâche Windows, IHM et lancement manuel.
[CmdletBinding()]
param(
    [string]$WorkspacePath,
    [string]$PythonExePath,
    [string]$LogFile,
    [string]$EnvFilePath,
    [switch]$IgnoreRunDays
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if (-not $WorkspacePath) {
    $WorkspacePath = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
}
$launcher = Join-Path $PSScriptRoot 'forward_pit_launcher.ps1'
if (-not (Test-Path -LiteralPath $launcher)) {
    throw "Launcher Forward PIT introuvable: $launcher"
}

$arguments = @('-BatchName', 'market_cap_sync', '-WorkspacePath', $WorkspacePath)
if ($PythonExePath) { $arguments += @('-PythonExePath', $PythonExePath) }
if ($LogFile) { $arguments += @('-LogFile', $LogFile) }
if ($EnvFilePath) { $arguments += @('-EnvFilePath', $EnvFilePath) }
if ($IgnoreRunDays) { $arguments += '-Force' }

& $launcher @arguments
exit $LASTEXITCODE
