# Lance P0j et journalise son statut. Point d'entrée de la tâche Windows.
[CmdletBinding()]
param(
    [string]$WorkspacePath,
    [string]$PythonExePath,
    [string]$ConfigPath,
    [string]$LogFile,
    [string]$EnvFilePath
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not $WorkspacePath) { $WorkspacePath = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$workspace = (Resolve-Path -LiteralPath $WorkspacePath).Path
if (-not $PythonExePath) { $PythonExePath = Join-Path $workspace '.venv\Scripts\python.exe' }
if (-not (Test-Path -LiteralPath $PythonExePath)) { throw "Python introuvable: $PythonExePath" }
if (-not $ConfigPath) { $ConfigPath = Join-Path $workspace 'config\oracle_canary.yaml' }
if (-not $LogFile) { $LogFile = Join-Path $workspace 'log\batch\oracle_canary.txt' }
$logDir = Split-Path -Parent $LogFile
if (-not (Test-Path -LiteralPath $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

function Write-Status([string]$Line) { Add-Content -LiteralPath $LogFile -Value $Line -Encoding UTF8 }
function Import-Env([string]$Path) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { return }
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $value = $line.Trim()
        if (-not $value -or $value.StartsWith('#')) { continue }
        $index = $value.IndexOf('=')
        if ($index -lt 1) { continue }
        $key = $value.Substring(0, $index).Trim()
        $content = $value.Substring($index + 1).Trim().Trim('"').Trim("'")
        if ($key) { Set-Item -Path ("Env:{0}" -f $key) -Value $content }
    }
}
if (-not $EnvFilePath) { $EnvFilePath = Join-Path $workspace '.env' }
Import-Env $EnvFilePath
$started = Get-Date
Write-Status ("[{0}] DEBUT P0j Oracle canary pid={1}" -f $started.ToString('yyyy-MM-dd HH:mm:ss'), $PID)
$exitCode = 0
try {
    Push-Location $workspace
    try {
        $env:PYTHONIOENCODING = 'utf-8'
        [Console]::OutputEncoding = [System.Text.Encoding]::UTF8
        # PowerShell 7 convertit parfois une simple ligne stderr native en
        # ErrorRecord. Avec ErrorActionPreference=Stop, l'avertissement PyTorch
        # « triton not found » interromprait alors le launcher malgré exit=0.
        $previousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        try {
            $captured = @(& $PythonExePath -u -m modelFactory.oracle_canary --config $ConfigPath 2>&1 |
                ForEach-Object {
                    $line = $_.ToString()
                    Write-Status $line
                    $line
                })
            $exitCode = $LASTEXITCODE
        } finally {
            $ErrorActionPreference = $previousErrorActionPreference
        }
    } finally { Pop-Location }
} catch {
    $exitCode = 1
    Write-Status ("[{0}] ERROR {1}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $_.Exception.Message)
}
$duration = (Get-Date) - $started
$status = if ($exitCode -eq 0) { 'OK' } else { 'ERROR' }
Write-Status ("[{0}] FIN P0j {1} exit={2} duree={3:hh\:mm\:ss}" -f (Get-Date).ToString('yyyy-MM-dd HH:mm:ss'), $status, $exitCode, $duration)
exit $exitCode
