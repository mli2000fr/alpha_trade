[CmdletBinding()]
param(
    [string]$WorkspacePath = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$PythonExePath,
    [string]$EnvFilePath,
    [string]$SecretStorePath,
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

function Resolve-OptionalExistingPath {
    param(
        [string]$ExplicitPath,
        [string[]]$Candidates
    )

    if ($ExplicitPath) {
        if (-not (Test-Path -LiteralPath $ExplicitPath)) {
            throw "Fichier introuvable: $ExplicitPath"
        }
        return (Resolve-Path -LiteralPath $ExplicitPath).Path
    }

    foreach ($candidate in $Candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    return $null
}

function Convert-SecureStringToPlainText {
    param([System.Security.SecureString]$SecureValue)

    if ($null -eq $SecureValue) {
        return ""
    }
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    }
    finally {
        if ($bstr -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
        }
    }
}

function Get-AlphaTradeDapiScopeValue {
    param([string]$ScopeName)

    if ($ScopeName -eq 'LocalMachine') {
        return [System.Security.Cryptography.DataProtectionScope]::LocalMachine
    }
    return [System.Security.Cryptography.DataProtectionScope]::CurrentUser
}

function Unprotect-AlphaTradeSecretValue {
    param(
        [string]$EncodedValue,
        [string]$ScopeName = 'CurrentUser'
    )

    $cipherBytes = [Convert]::FromBase64String($EncodedValue)
    $entropy = [Text.Encoding]::UTF8.GetBytes('AlphaTradeProtectionWatcher')
    $plainBytes = [System.Security.Cryptography.ProtectedData]::Unprotect(
        $cipherBytes,
        $entropy,
        (Get-AlphaTradeDapiScopeValue -ScopeName $ScopeName)
    )
    return [Text.Encoding]::UTF8.GetString($plainBytes)
}

function Import-AlphaTradeEnvFile {
    param([string]$Path)

    if (-not $Path) {
        return
    }

    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith('#')) {
            continue
        }
        $separatorIndex = $trimmed.IndexOf('=')
        if ($separatorIndex -lt 1) {
            continue
        }
        $key = $trimmed.Substring(0, $separatorIndex).Trim()
        $value = $trimmed.Substring($separatorIndex + 1).Trim()
        if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
            $value = $value.Substring(1, $value.Length - 2)
        }
        if ($key) {
            Set-Item -Path ("Env:{0}" -f $key) -Value $value
        }
    }
}

function Import-AlphaTradeSecretStore {
    param([string]$Path)

    if (-not $Path) {
        return
    }

    $rawPayload = Get-Content -LiteralPath $Path -Encoding UTF8 -Raw
    if (-not $rawPayload.Trim()) {
        return
    }
    $payload = ConvertFrom-Json -InputObject $rawPayload
    if ($null -eq $payload) {
        return
    }

    $scopeName = 'CurrentUser'
    if ($payload.PSObject.Properties.Name -contains 'dpapiScope' -and $payload.dpapiScope) {
        $scopeName = [string]$payload.dpapiScope
    }

    if (-not ($payload.PSObject.Properties.Name -contains 'secrets') -or $null -eq $payload.secrets) {
        return
    }

    foreach ($property in $payload.secrets.PSObject.Properties) {
        $secretName = [string]$property.Name
        $secretValue = [string]$property.Value
        if (-not $secretName -or -not $secretValue) {
            continue
        }
        $plainValue = Unprotect-AlphaTradeSecretValue -EncodedValue $secretValue -ScopeName $scopeName
        Set-Item -Path ("Env:{0}" -f $secretName) -Value $plainValue
    }
}

$resolvedWorkspace = (Resolve-Path -LiteralPath $WorkspacePath).Path
$resolvedEnvFile = Resolve-OptionalExistingPath -ExplicitPath $EnvFilePath -Candidates @(
    (Join-Path $PSScriptRoot 'protection_watcher.env'),
    (Join-Path $resolvedWorkspace '.env'),
    (Join-Path $resolvedWorkspace '.env.watcher')
)
$resolvedSecretStore = Resolve-OptionalExistingPath -ExplicitPath $SecretStorePath -Candidates @(
    (Join-Path $resolvedWorkspace 'artifacts\windows_secrets\protection_watcher.secrets.json'),
    (Join-Path $PSScriptRoot 'protection_watcher.secrets.json'),
    $(if ($env:ProgramData) { Join-Path $env:ProgramData 'AlphaTrade\protection_watcher.secrets.json' } else { $null }),
    $(if ($env:APPDATA) { Join-Path $env:APPDATA 'AlphaTrade\protection_watcher.secrets.json' } else { $null })
)

Import-AlphaTradeEnvFile -Path $resolvedEnvFile
Import-AlphaTradeSecretStore -Path $resolvedSecretStore

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

