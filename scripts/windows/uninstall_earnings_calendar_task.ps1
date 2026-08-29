# uninstall_earnings_calendar_task.ps1
#
# Supprime la tâche planifiée Windows « AlphaTrade-EarningsCalendarSync ».
#
# Usage :
#   powershell -ExecutionPolicy Bypass -File .\scripts\windows\uninstall_earnings_calendar_task.ps1
[CmdletBinding()]
param(
    [string]$TaskName = 'AlphaTrade-EarningsCalendarSync'
)

$ErrorActionPreference = 'Stop'

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($task) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Host "Tâche supprimée: $TaskName" -ForegroundColor Green
} else {
    Write-Host "Aucune tâche planifiée nommée '$TaskName'."
}
