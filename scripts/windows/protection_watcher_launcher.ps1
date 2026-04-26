[CmdletBinding()]
param(
    [string]$WorkspacePath = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$PythonExePath,
    [ValidateSet('once', 'service')]
    [string]$Mode = 'once',
    [string]$Account,
    [string]$ExecRunId,
    [int]$Limit = 100,
    [double]$ServiceIntervalSeconds = 30.0,
    [double]$IdleIntervalSeconds = 120.0,
    [double]$HeartbeatIntervalSeconds = 300.0,
    [Nullable[int]]$MaxIterations = $null,
    [switch]$StopWhenIdle,
    [int]$MaxConsecutiveFailures = 3,
    [ValidateSet('INFO', 'DEBUG', 'WARNING', 'ERROR')]
    [string]$LogLevel = 'INFO',
    [string]$StdoutPath,
    [string]$StderrPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Resolve-AlphaTradePythonExe {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Workspace,
        [string]$RequestedPythonExePath
    )

    if ($RequestedPythonExePath) {
        if (-not (Test-Path -LiteralPath $RequestedPythonExePath)) {
            throw "Python introuvable: $RequestedPythonExePath"
        }
        return (Resolve-Path -LiteralPath $RequestedPythonExePath).Path
    }

    $candidates = @(
        (Join-Path $Workspace '.venv\Scripts\python.exe'),
        (Join-Path $Workspace 'venv\Scripts\python.exe'),
        (Join-Path $Workspace '.python\Scripts\python.exe')
    )

    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }

    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand) {
        return $pythonCommand.Source
    }

    $pyLauncher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($pyLauncher) {
        return $pyLauncher.Source
    }

    throw 'Aucun interpréteur Python exploitable trouvé. Fournir -PythonExePath ou créer .venv\Scripts\python.exe.'
}

function Ensure-ParentDirectory {
    param([string]$Path)

    if (-not $Path) {
        return
    }
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
}

$resolvedWorkspace = (Resolve-Path -LiteralPath $WorkspacePath).Path
$resolvedPython = Resolve-AlphaTradePythonExe -Workspace $resolvedWorkspace -RequestedPythonExePath $PythonExePath
$watcherScript = Join-Path $resolvedWorkspace 'run_execution_protection_watch.py'
if (-not (Test-Path -LiteralPath $watcherScript)) {
    throw "Entrée watcher introuvable: $watcherScript"
}

$pythonArgs = @(
    $watcherScript,
    '--mode', $Mode,
    '--limit', [string]$Limit,
    '--service-interval-seconds', [string]$ServiceIntervalSeconds,
    '--idle-interval-seconds', [string]$IdleIntervalSeconds,
    '--heartbeat-interval-seconds', [string]$HeartbeatIntervalSeconds,
    '--max-consecutive-failures', [string]$MaxConsecutiveFailures,
    '--log-level', $LogLevel
)

if ($Account) {
    $pythonArgs += @('--account', $Account)
}
if ($ExecRunId) {
    $pythonArgs += @('--exec-run-id', $ExecRunId)
}
if ($MaxIterations -ne $null) {
    $pythonArgs += @('--max-iterations', [string]$MaxIterations)
}
if ($StopWhenIdle.IsPresent) {
    $pythonArgs += '--stop-when-idle'
}

Push-Location $resolvedWorkspace
try {
    if ($StdoutPath -or $StderrPath) {
        Ensure-ParentDirectory -Path $StdoutPath
        Ensure-ParentDirectory -Path $StderrPath

        $startProcessParams = @{
            FilePath         = $resolvedPython
            ArgumentList     = $pythonArgs
            WorkingDirectory = $resolvedWorkspace
            Wait             = $true
            PassThru         = $true
            NoNewWindow      = $true
        }
        if ($StdoutPath) {
            $startProcessParams.RedirectStandardOutput = $StdoutPath
        }
        if ($StderrPath) {
            $startProcessParams.RedirectStandardError = $StderrPath
        }

        $process = Start-Process @startProcessParams
        exit $process.ExitCode
    }

    & $resolvedPython @pythonArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}

