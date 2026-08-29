[CmdletBinding()]
param(
    [string]$TaskName = 'AlphaTrade-ProtectionWatcher'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $existingTask) {
    Write-Host "Aucune tâche Task Scheduler à supprimer pour: $TaskName" -ForegroundColor Yellow
    return
}

Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Task Scheduler supprimé: $TaskName" -ForegroundColor Green

