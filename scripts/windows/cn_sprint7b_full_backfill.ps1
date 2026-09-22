param(
    [int]$WaitForProcessId = 0,
    [int]$StartChunk = 0
)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$artifactRoot = Join-Path $projectRoot "artifacts\cn\sprint7b"
$lockPath = Join-Path $artifactRoot "full_backfill.lock"

New-Item -ItemType Directory -Force -Path $artifactRoot | Out-Null

if ($WaitForProcessId -gt 0) {
    Write-Output "Attente du processus pilote $WaitForProcessId"
    Wait-Process -Id $WaitForProcessId -ErrorAction SilentlyContinue
}

$lock = $null
try {
    $lock = [System.IO.File]::Open($lockPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    $payload = [Text.Encoding]::UTF8.GetBytes("pid=$PID started_at=$([DateTimeOffset]::Now.ToString('o'))")
    $lock.Write($payload, 0, $payload.Length)
    $lock.Flush()

    Set-Location $projectRoot
    Write-Output "Sprint 7-B backfill start: $([DateTimeOffset]::Now.ToString('o'))"
    & $python -u -m dataIntegrityEngine.cn_sprint7b_full run-all --start-chunk $StartChunk --log-level INFO
    $exitCode = $LASTEXITCODE
    Write-Output "Sprint 7-B backfill end: $([DateTimeOffset]::Now.ToString('o')) exit=$exitCode"
    exit $exitCode
}
catch [System.IO.IOException] {
    Write-Error "Un backfill Sprint 7-B détient déjà le verrou $lockPath"
    exit 3
}
finally {
    if ($null -ne $lock) {
        $lock.Dispose()
        Remove-Item -LiteralPath $lockPath -Force -ErrorAction SilentlyContinue
    }
}
