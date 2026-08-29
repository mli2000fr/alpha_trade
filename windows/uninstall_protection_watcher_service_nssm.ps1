[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$NssmExePath,
    [string]$ServiceName = 'AlphaTradeProtectionWatcher'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if (-not (Test-Path -LiteralPath $NssmExePath)) {
    throw "NSSM introuvable: $NssmExePath"
}

$existingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if (-not $existingService) {
    Write-Host "Aucun service NSSM à supprimer pour: $ServiceName" -ForegroundColor Yellow
    return
}

try {
    & $NssmExePath stop $ServiceName | Out-Null
}
catch {
    Write-Warning "Impossible d'arrêter proprement $ServiceName avant suppression: $($_.Exception.Message)"
}

& $NssmExePath remove $ServiceName confirm | Out-Null
Write-Host "Service NSSM supprimé: $ServiceName" -ForegroundColor Green

