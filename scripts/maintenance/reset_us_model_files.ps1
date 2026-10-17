[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$taskWorkspace = [System.IO.Path]::GetFullPath('F:\projets')
$taskArtifacts = [System.IO.Path]::GetFullPath('F:\projets\artifacts')
$taskOperation = 'F:\projets\artifacts\operations\us_models_reset\20261013-v1'
$taskPlanPath = Join-Path $taskOperation 'plan.json'
$taskPlan = Get-Content -LiteralPath $taskPlanPath -Raw | ConvertFrom-Json
$taskDatabase = Get-Content -LiteralPath (Join-Path $taskOperation 'database-progress.json') -Raw | ConvertFrom-Json
if ($taskPlan.schema -ne 'alpha_trade' -or $taskPlan.filesystem_action -ne 'DELETE' -or $taskDatabase.status -ne 'COMPLETED') {
    throw 'Explicit US database reset and direct-deletion plan required.'
}
$taskPlanHash = (Get-FileHash -LiteralPath $taskPlanPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($taskPlanHash -ne $taskDatabase.plan_sha256) { throw 'Plan changed after database reset.' }
$taskTargets = @()
foreach ($taskEntry in $taskPlan.filesystem) {
    $taskPath = [System.IO.Path]::GetFullPath([string]$taskEntry.source)
    if (-not $taskPath.StartsWith(($taskArtifacts + '\'), [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Target outside verified artefacts directory: $taskPath"
    }
    $taskRelative = $taskPath.Substring($taskArtifacts.Length + 1)
    $taskParts = @($taskRelative -split '[\\/]')
    if ($taskParts.Count -lt 2 -or $taskParts[0] -in @('cn','fr','operations','backups')) {
        throw "Protected or broad target: $taskPath"
    }
    foreach ($taskPart in $taskParts) {
        if ($taskPart -match '^(cn_|fr_)') { throw "Non-US target: $taskPath" }
    }
    if (Test-Path -LiteralPath $taskPath) {
        $taskItem = Get-Item -LiteralPath $taskPath -Force
        if (($taskItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw "Reparse-point target: $taskPath"
        }
        if ($taskItem.PSIsContainer) {
            $taskLinks = Get-ChildItem -LiteralPath $taskPath -Recurse -Force -Attributes ReparsePoint
            if ($taskLinks) { throw "Reparse point inside recursive target: $taskPath" }
        }
        $taskResolved = (Resolve-Path -LiteralPath $taskPath).ProviderPath
        if (-not $taskResolved.Equals($taskPath, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Resolved target differs: $taskPath"
        }
    }
    $taskTargets += $taskPath
}
# All paths are validated before the first recursive delete, in this shell only.
$taskDeleted = 0
$taskAlreadyAbsent = 0
foreach ($taskPath in $taskTargets) {
    if (Test-Path -LiteralPath $taskPath) {
        Remove-Item -LiteralPath $taskPath -Recurse -Force
        if (Test-Path -LiteralPath $taskPath) { throw "Target remains: $taskPath" }
        $taskDeleted++
    } else {
        $taskAlreadyAbsent++
    }
}
$taskResult = [ordered]@{
    status = 'COMPLETED'
    plan_sha256 = $taskPlanHash
    deleted_targets = $taskDeleted
    already_absent = $taskAlreadyAbsent
    archive_created = $false
    remaining_targets = @($taskTargets | Where-Object { Test-Path -LiteralPath $_ })
}
$taskResult | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $taskOperation 'filesystem-progress.json') -Encoding utf8
$taskResult | ConvertTo-Json -Depth 5
