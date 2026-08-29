[CmdletBinding()]
param(
    [string]$WorkspacePath = (Split-Path -Parent (Split-Path -Parent $PSScriptRoot)),
    [string]$TaskName = 'AlphaTrade-ProtectionWatcher',
    [string]$ServiceName = 'AlphaTradeProtectionWatcher'
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Resolve-ExistingPathOrNull {
    param([string]$PathValue)

    if (-not $PathValue) {
        return $null
    }
    if (Test-Path -LiteralPath $PathValue) {
        return (Resolve-Path -LiteralPath $PathValue).Path
    }
    return $PathValue
}

function Get-ArgumentValue {
    param(
        [string]$Arguments,
        [string]$Name
    )

    if (-not $Arguments -or -not $Name) {
        return $null
    }

    $pattern = '(?i)(?:^|\s)-' + [Regex]::Escape($Name) + '\s+(?:"([^"]+)"|''([^'']+)''|([^\s]+))'
    $match = [Regex]::Match($Arguments, $pattern)
    if (-not $match.Success) {
        return $null
    }

    foreach ($groupIndex in 1..3) {
        $value = $match.Groups[$groupIndex].Value
        if ($value) {
            return $value
        }
    }
    return $null
}

function Build-LogSourceRecord {
    param(
        [string]$Source,
        [string]$Runtime,
        [string]$Kind,
        [string]$PathValue
    )

    if (-not $PathValue) {
        return $null
    }

    $resolved = Resolve-ExistingPathOrNull -PathValue $PathValue
    $exists = $false
    if ($resolved) {
        $exists = Test-Path -LiteralPath $resolved
    }

    return @{
        source = $Source
        runtime = $Runtime
        kind = $Kind
        path = $resolved
        exists = $exists
    }
}

$resolvedWorkspace = Resolve-ExistingPathOrNull -PathValue $WorkspacePath
if (-not $resolvedWorkspace) {
    $resolvedWorkspace = $WorkspacePath
}

$payload = @{
    generatedAt = (Get-Date).ToString('s')
    workspacePath = $resolvedWorkspace
    bridge = @{
        script = 'get_protection_watcher_status.ps1'
        mode = 'read_only'
        allowlist = @('status', 'log_import')
    }
    task = @{
        name = $TaskName
        exists = $false
        state = 'not_found'
        enabled = $null
        lastRunTime = $null
        nextRunTime = $null
        lastTaskResult = $null
        stdoutPath = Resolve-ExistingPathOrNull -PathValue (Join-Path $resolvedWorkspace 'log\windows_scheduler\protection_watcher_task_stdout.log')
        stderrPath = Resolve-ExistingPathOrNull -PathValue (Join-Path $resolvedWorkspace 'log\windows_scheduler\protection_watcher_task_stderr.log')
        actionArguments = $null
        error = $null
    }
    service = @{
        name = $ServiceName
        exists = $false
        status = 'not_found'
        startType = $null
        displayName = $null
        stdoutPath = Resolve-ExistingPathOrNull -PathValue (Join-Path $resolvedWorkspace 'log\windows_service\protection_watcher_service_stdout.log')
        stderrPath = Resolve-ExistingPathOrNull -PathValue (Join-Path $resolvedWorkspace 'log\windows_service\protection_watcher_service_stderr.log')
        error = $null
    }
    logSources = @()
}

try {
    $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction Stop
    $taskInfo = Get-ScheduledTaskInfo -TaskName $TaskName -TaskPath $task.TaskPath -ErrorAction Stop
    $taskAction = $task.Actions | Select-Object -First 1
    $taskArguments = if ($taskAction) { [string]$taskAction.Arguments } else { '' }
    $taskStdout = Get-ArgumentValue -Arguments $taskArguments -Name 'StdoutPath'
    $taskStderr = Get-ArgumentValue -Arguments $taskArguments -Name 'StderrPath'
    if ($taskStdout) {
        $payload.task.stdoutPath = Resolve-ExistingPathOrNull -PathValue $taskStdout
    }
    if ($taskStderr) {
        $payload.task.stderrPath = Resolve-ExistingPathOrNull -PathValue $taskStderr
    }
    $payload.task.exists = $true
    $payload.task.state = [string]$task.State
    $payload.task.enabled = [bool]$task.Settings.Enabled
    $payload.task.lastRunTime = if ($taskInfo.LastRunTime) { $taskInfo.LastRunTime.ToString('s') } else { $null }
    $payload.task.nextRunTime = if ($taskInfo.NextRunTime) { $taskInfo.NextRunTime.ToString('s') } else { $null }
    $payload.task.lastTaskResult = [string]$taskInfo.LastTaskResult
    $payload.task.actionArguments = $taskArguments
}
catch {
    $payload.task.error = $_.Exception.Message
}

try {
    $service = Get-Service -Name $ServiceName -ErrorAction Stop
    $serviceDetails = Get-CimInstance Win32_Service -Filter ("Name='{0}'" -f $ServiceName) -ErrorAction SilentlyContinue
    $serviceParametersKey = "HKLM:\SYSTEM\CurrentControlSet\Services\$ServiceName\Parameters"
    $serviceParameters = Get-ItemProperty -Path $serviceParametersKey -ErrorAction SilentlyContinue
    if ($serviceParameters -and $serviceParameters.PSObject.Properties.Name -contains 'AppStdout' -and $serviceParameters.AppStdout) {
        $payload.service.stdoutPath = Resolve-ExistingPathOrNull -PathValue ([string]$serviceParameters.AppStdout)
    }
    if ($serviceParameters -and $serviceParameters.PSObject.Properties.Name -contains 'AppStderr' -and $serviceParameters.AppStderr) {
        $payload.service.stderrPath = Resolve-ExistingPathOrNull -PathValue ([string]$serviceParameters.AppStderr)
    }
    $payload.service.exists = $true
    $payload.service.status = [string]$service.Status
    $payload.service.displayName = [string]$service.DisplayName
    if ($serviceDetails) {
        $payload.service.startType = [string]$serviceDetails.StartMode
    }
}
catch {
    $payload.service.error = $_.Exception.Message
}

$logSources = @(
    (Build-LogSourceRecord -Source 'Task Scheduler stdout' -Runtime 'task' -Kind 'stdout' -PathValue ([string]$payload.task.stdoutPath)),
    (Build-LogSourceRecord -Source 'Task Scheduler stderr' -Runtime 'task' -Kind 'stderr' -PathValue ([string]$payload.task.stderrPath)),
    (Build-LogSourceRecord -Source 'NSSM stdout' -Runtime 'service' -Kind 'stdout' -PathValue ([string]$payload.service.stdoutPath)),
    (Build-LogSourceRecord -Source 'NSSM stderr' -Runtime 'service' -Kind 'stderr' -PathValue ([string]$payload.service.stderrPath))
) | Where-Object { $null -ne $_ }
$payload.logSources = @($logSources)

$payload | ConvertTo-Json -Depth 6

