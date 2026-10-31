param(
    [ValidateSet('restore','verify','recover')][string]$Action = 'restore',
    [string]$Python = 'python',
    [string]$BackupDir = '',
    [string]$TargetDir = ''
)
$ErrorActionPreference = 'Stop'
# The backup contains a standalone copy: no existing Alpha Trade installation needed.
# No password is accepted on the command line or written to a request file.
$toolRoot = Join-Path $PSScriptRoot 'outils'
$runtimeRoot = Join-Path $PSScriptRoot '.outils-python'
$runtimePython = Join-Path $runtimeRoot 'Scripts\python.exe'
if (-not $BackupDir -and $Action -ne 'recover') { $BackupDir = $PSScriptRoot }
if ($BackupDir) { $BackupDir = (Resolve-Path -LiteralPath $BackupDir).Path }
if (-not (Test-Path -LiteralPath $runtimePython)) {
    & $Python -m venv $runtimeRoot
    if ($LASTEXITCODE -ne 0) { throw 'Installer la même version majeure.mineure de Python que la source.' }
    & $runtimePython -m pip install -r (Join-Path $toolRoot 'requirements-migration.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Installation des outils de restauration impossible.' }
}
Push-Location -LiteralPath $toolRoot
try {
    $migrationArguments = @($Action)
    if ($BackupDir) { $migrationArguments += @('--backup-dir', $BackupDir) }
    if ($TargetDir) { $migrationArguments += @('--target-dir', $TargetDir) }
    & $runtimePython -X utf8 -m portable_migration.cli @migrationArguments
    if ($LASTEXITCODE -ne 0) { throw 'Restauration non terminée ; consulter son rapport.' }
} finally { Pop-Location }
