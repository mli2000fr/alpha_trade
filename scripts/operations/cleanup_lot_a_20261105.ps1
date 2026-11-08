param(
    [Parameter(Mandatory=$true)][string]$PlanPath,
    [Parameter(Mandatory=$true)][string]$ExpectedSha256,
    [Parameter(Mandatory=$true)][string]$ReportDirectory,
    [switch]$Execute
)
$ErrorActionPreference = 'Stop'
$workspaceRoot = [IO.Path]::GetFullPath('F:\projets').TrimEnd('\')
$workspacePrefix = $workspaceRoot + '\'
$planFile = (Resolve-Path -LiteralPath $PlanPath).Path
if ((Get-FileHash -LiteralPath $planFile -Algorithm SHA256).Hash -ne $ExpectedSha256) {
    throw 'Le plan ne correspond plus au lot A approuvé.'
}
$cleanupPlan = Get-Content -LiteralPath $planFile -Raw | ConvertFrom-Json
if ([IO.Path]::GetFullPath($cleanupPlan.root).TrimEnd('\') -ne $workspaceRoot) { throw 'Racine du plan incorrecte.' }
$auditCutoff = [DateTimeOffset]::Parse($cleanupPlan.audit_at_utc).UtcDateTime
$reportRoot = [IO.Path]::GetFullPath($ReportDirectory)
if (-not $reportRoot.StartsWith($workspacePrefix,[StringComparison]::OrdinalIgnoreCase)) { throw 'Rapport hors projet.' }
if (Test-Path -LiteralPath $reportRoot) { throw 'Utiliser un nouveau dossier de bilan.' }
New-Item -ItemType Directory -Path $reportRoot | Out-Null
$protected = @('.git','.venv','config','conf','doc','prompt','backups','artifacts\models',
    'artifacts\research','artifacts\fr','artifacts\cn','artifacts\sec_cache',
    'artifacts\intraday_backfill','artifacts\options_directional','artifacts\llm_directional','artifacts\config_vault')
$tracked = @(& git -C $workspaceRoot ls-files --)
if ($LASTEXITCODE -ne 0) { throw 'Lecture index Git impossible.' }
$results = [Collections.Generic.List[object]]::new()
$removedBytes = [long]0
$removedFiles = [long]0
$index = 0
function Inspect-Candidate([string]$absolutePath) {
    $item = Get-Item -LiteralPath $absolutePath -Force
    $pending = [Collections.Generic.Stack[IO.FileSystemInfo]]::new()
    $pending.Push($item)
    $bytes = [long]0; $files = [long]0; $newest = [DateTime]::MinValue
    while ($pending.Count -gt 0) {
        $current = $pending.Pop()
        if (($current.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Lien ou jonction rencontré.' }
        if (-not $current.FullName.StartsWith($workspacePrefix,[StringComparison]::OrdinalIgnoreCase)) { throw 'Chemin descendant hors projet.' }
        if ($current.LastWriteTimeUtc -gt $newest) { $newest = $current.LastWriteTimeUtc }
        if ($current -is [IO.DirectoryInfo]) {
            foreach ($child in $current.EnumerateFileSystemInfos()) { $pending.Push($child) }
        } else { $bytes += $current.Length; $files++ }
    }
    return @{bytes=$bytes;files=$files;newest=$newest}
}
foreach ($entry in $cleanupPlan.entries) {
    $index++
    $absolute = [IO.Path]::GetFullPath([string]$entry.path)
    $result = [ordered]@{path=$absolute;status='PENDING';bytes=0;files=0}
    try {
        if (-not $absolute.StartsWith($workspacePrefix,[StringComparison]::OrdinalIgnoreCase)) { throw 'Cible hors projet.' }
        $relative = $absolute.Substring($workspacePrefix.Length)
        if ($relative.Replace('\','/') -ne $entry.relative_path) { throw 'Chemins du plan incompatibles.' }
        foreach ($prefix in $protected) {
            if ($relative -eq $prefix -or $relative.StartsWith($prefix+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Périmètre protégé.' }
        }
        foreach ($versioned in $tracked) {
            $versioned = $versioned.Replace('/','\')
            if ($versioned -eq $relative -or $versioned.StartsWith($relative+'\',[StringComparison]::OrdinalIgnoreCase)) { throw 'Fichier Git présent dans la cible.' }
        }
        if (-not (Test-Path -LiteralPath $absolute)) { $result.status='ALREADY_ABSENT' }
        else {
            $resolved = (Resolve-Path -LiteralPath $absolute).Path
            if (-not $resolved.StartsWith($workspacePrefix,[StringComparison]::OrdinalIgnoreCase)) { throw 'Cible résolue hors projet.' }
            $current = Inspect-Candidate $absolute
            if ($current.bytes -ne [long]$entry.bytes -or $current.files -ne [long]$entry.files -or $current.newest -gt $auditCutoff) {
                $result.status='SKIPPED_CHANGED'
                $result.bytes=$current.bytes; $result.files=$current.files
            } elseif ($Execute) {
                if ($entry.kind -eq 'directory') { Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction Stop }
                elseif ($entry.kind -eq 'file') { Remove-Item -LiteralPath $resolved -Force -ErrorAction Stop }
                else { throw 'Type de cible inconnu.' }
                $result.status='REMOVED';$result.bytes=$current.bytes;$result.files=$current.files
                $removedBytes += $current.bytes;$removedFiles += $current.files
            } else { $result.status='READY';$result.bytes=$current.bytes;$result.files=$current.files }
        }
    } catch { $result.status='SKIPPED_ERROR';$result.error_type=$_.Exception.GetType().Name }
    $results.Add([pscustomobject]$result)
    ($result | ConvertTo-Json -Compress) | Add-Content -LiteralPath (Join-Path $reportRoot 'targets.jsonl') -Encoding utf8
    if ($index % 40 -eq 0) {
        Write-Output ("{0}/{1} cibles ; {2:N3} Go supprimés" -f $index,$cleanupPlan.entries.Count,($removedBytes/1e9))
    }
}
$summary = [ordered]@{status=$(if ($Execute) {'COMPLETED'} else {'PREVIEW'});executed=[bool]$Execute;
    approved_scope='LOT_A_ONLY';plan_sha256=$ExpectedSha256;finished_at_utc=[DateTimeOffset]::UtcNow.ToString('o');
    targets=$index;removed_bytes=$removedBytes;removed_files=$removedFiles;
    statuses=@($results | Group-Object status | ForEach-Object { @{status=$_.Name;count=$_.Count} });
    SQL_writes=$false;source_services_stopped=$false}
$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $reportRoot 'report.json') -Encoding utf8
$summary | ConvertTo-Json -Depth 8
