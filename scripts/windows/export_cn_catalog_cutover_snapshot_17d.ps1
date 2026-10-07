# Snapshot de retour arrière 17-D : lecture du planificateur, aucune modification de tâche.
[CmdletBinding()]
param(
    [string]$WorkspacePath,
    [string]$OutputRoot
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if (-not $WorkspacePath) { $WorkspacePath = Split-Path -Parent (Split-Path -Parent $PSScriptRoot) }
$workspace = (Resolve-Path -LiteralPath $WorkspacePath).Path
if (-not $OutputRoot) { $OutputRoot = Join-Path $workspace 'artifacts/research/cn_operations_17a/cutover_snapshots' }
if (-not [IO.Path]::IsPathRooted($OutputRoot)) { $OutputRoot = Join-Path $workspace $OutputRoot }

$names = @(
    'AlphaTrade-CnDragonTigerBeforeOpen',
    'AlphaTrade-CnDragonTigerDailyMatch',
    'AlphaTrade-CnDragonTigerAfterClose',
    'AlphaTrade-CnOracleProspectiveDaily'
)
$tasks = @()
foreach ($name in $names) {
    $task = Get-ScheduledTask -TaskName $name -ErrorAction Stop
    if ($task.State -eq 'Running') { throw "Tâche CN en cours : $name" }
    $tasks += $task
}

$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$target = Join-Path $OutputRoot $stamp
if (Test-Path -LiteralPath $target) { throw "Snapshot déjà présent : $target" }
New-Item -ItemType Directory -Path $target -Force | Out-Null

$files = @()
foreach ($catalog in @('batch.yaml', 'batch_cn.yaml')) {
    $source = Join-Path $workspace $catalog
    $destination = Join-Path $target $catalog
    Copy-Item -LiteralPath $source -Destination $destination -ErrorAction Stop
    $files += [pscustomobject]@{
        name = $catalog
        sha256 = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
    }
}

$taskRows = @()
foreach ($task in $tasks) {
    $name = $task.TaskName
    $destination = Join-Path $target "$name.xml"
    $xml = Export-ScheduledTask -TaskName $name -ErrorAction Stop
    # Export-ScheduledTask déclare UTF-16 dans l'en-tête XML : préserver
    # cet encodage pour qu'un import Windows ultérieur soit réellement valide.
    [IO.File]::WriteAllText($destination, $xml, [Text.Encoding]::Unicode)
    $info = Get-ScheduledTaskInfo -TaskName $name -ErrorAction Stop
    $files += [pscustomobject]@{
        name = "$name.xml"
        sha256 = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
    }
    $taskRows += [pscustomobject]@{
        name = $name
        state = [string]$task.State
        last_result = $info.LastTaskResult
        last_run = [string]$info.LastRunTime
        next_run = [string]$info.NextRunTime
        action_count = @($task.Actions).Count
        trigger_count = @($task.Triggers).Count
        logon_type = [string]$task.Principal.LogonType
    }
}

$manifest = [ordered]@{
    purpose = 'CN_17D_PRE_CUTOVER_ROLLBACK_SNAPSHOT'
    created_at_utc = [DateTimeOffset]::UtcNow.ToString('o')
    task_definitions_exported = $taskRows.Count
    catalogs_modified = $false
    scheduler_changed = $false
    files = $files
    tasks = $taskRows
}
$manifestPath = Join-Path $target 'manifest.json'
$manifest | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $manifestPath -Encoding UTF8
Write-Output $manifestPath
