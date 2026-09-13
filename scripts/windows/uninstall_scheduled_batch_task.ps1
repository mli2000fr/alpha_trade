# Désinstalle uniquement une tâche planifiée AlphaTrade identifiée exactement.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)]
    [ValidatePattern('^AlphaTrade-[A-Za-z0-9_-]+$')]
    [string]$TaskName
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $task) {
    Write-Host "Tâche déjà absente: $TaskName"
    exit 0
}
if ([string]$task.State -eq 'Running') {
    throw "Désinstallation refusée: la tâche $TaskName est en cours d'exécution."
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Tâche désinstallée: $TaskName" -ForegroundColor Green
Write-Host "Les données, journaux et la configuration batch.yaml sont conservés."
