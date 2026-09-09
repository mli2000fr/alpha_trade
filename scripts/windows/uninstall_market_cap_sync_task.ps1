# Supprime la tâche planifiée AlphaTrade-MarketCapSync.
[CmdletBinding()]
param([string]$TaskName = 'AlphaTrade-MarketCapSync')

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Tâche supprimée: $TaskName" -ForegroundColor Green
} else {
    Write-Host "Aucune tâche planifiée nommée '$TaskName'."
}
