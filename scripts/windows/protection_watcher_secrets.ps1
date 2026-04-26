[CmdletBinding()]
param(
    [ValidateSet('Save', 'Remove', 'ShowMetadata')]
    [string]$Action = 'Save',
    [string]$StorePath,
    [ValidateSet('CurrentUser', 'LocalMachine')]
    [string]$DpapiScope = 'CurrentUser',
    [string[]]$SecretNames = @('LOGIN_DB', 'PASSWORD_DB', 'ALPACA_API_KEY', 'ALPACA_SECRET_KEY'),
    [switch]$FromEnvironment
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Get-DefaultSecretStorePath {
    param([string]$Scope)

    if ($Scope -eq 'LocalMachine' -and $env:ProgramData) {
        return (Join-Path $env:ProgramData 'AlphaTrade\protection_watcher.secrets.json')
    }
    if ($env:APPDATA) {
        return (Join-Path $env:APPDATA 'AlphaTrade\protection_watcher.secrets.json')
    }
    return (Join-Path (Get-Location).Path 'protection_watcher.secrets.json')
}

function Ensure-ParentDirectory {
    param([string]$Path)

    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
}

function Convert-SecureStringToPlainText {
    param([System.Security.SecureString]$SecureValue)

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

function Get-DpapiScopeValue {
    param([string]$ScopeName)

    if ($ScopeName -eq 'LocalMachine') {
        return [System.Security.Cryptography.DataProtectionScope]::LocalMachine
    }
    return [System.Security.Cryptography.DataProtectionScope]::CurrentUser
}

function Protect-SecretValue {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Value,
        [Parameter(Mandatory = $true)]
        [string]$ScopeName
    )

    $entropy = [Text.Encoding]::UTF8.GetBytes('AlphaTradeProtectionWatcher')
    $plainBytes = [Text.Encoding]::UTF8.GetBytes($Value)
    $cipherBytes = [System.Security.Cryptography.ProtectedData]::Protect(
        $plainBytes,
        $entropy,
        (Get-DpapiScopeValue -ScopeName $ScopeName)
    )
    return [Convert]::ToBase64String($cipherBytes)
}

function Resolve-SecretValue {
    param(
        [string]$Name,
        [switch]$UseEnvironment
    )

    if ($UseEnvironment.IsPresent) {
        $currentValue = [Environment]::GetEnvironmentVariable($Name)
        if (-not $currentValue) {
            throw "Variable d'environnement introuvable pour $Name"
        }
        return $currentValue
    }

    $secureValue = Read-Host -Prompt ("Valeur pour {0}" -f $Name) -AsSecureString
    return (Convert-SecureStringToPlainText -SecureValue $secureValue)
}

$resolvedStorePath = if ($StorePath) { $StorePath } else { Get-DefaultSecretStorePath -Scope $DpapiScope }

switch ($Action) {
    'Remove' {
        if (Test-Path -LiteralPath $resolvedStorePath) {
            Remove-Item -LiteralPath $resolvedStorePath -Force
            Write-Host "Secret store supprimé: $resolvedStorePath" -ForegroundColor Green
        }
        else {
            Write-Host "Aucun secret store à supprimer: $resolvedStorePath" -ForegroundColor Yellow
        }
        break
    }
    'ShowMetadata' {
        if (-not (Test-Path -LiteralPath $resolvedStorePath)) {
            throw "Secret store introuvable: $resolvedStorePath"
        }
        $payload = Get-Content -LiteralPath $resolvedStorePath -Encoding UTF8 -Raw | ConvertFrom-Json
        $secretCount = if ($payload.secrets) { @($payload.secrets.PSObject.Properties).Count } else { 0 }
        Write-Host "Store path  : $resolvedStorePath"
        Write-Host "DPAPI scope : $($payload.dpapiScope)"
        Write-Host "Created at  : $($payload.createdAt)"
        Write-Host "Secrets     : $secretCount"
        break
    }
    default {
        $secretPayload = [ordered]@{}
        foreach ($secretName in $SecretNames) {
            $plainValue = Resolve-SecretValue -Name $secretName -UseEnvironment:$FromEnvironment
            if (-not $plainValue) {
                throw "Valeur vide interdite pour $secretName"
            }
            $secretPayload[$secretName] = Protect-SecretValue -Value $plainValue -ScopeName $DpapiScope
        }

        Ensure-ParentDirectory -Path $resolvedStorePath
        $payload = [ordered]@{
            version    = 1
            createdAt  = (Get-Date).ToString('o')
            dpapiScope = $DpapiScope
            secrets    = $secretPayload
        }
        $payload | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $resolvedStorePath -Encoding UTF8

        Write-Host "Secret store écrit: $resolvedStorePath" -ForegroundColor Green
        Write-Host "DPAPI scope       : $DpapiScope"
        if ($DpapiScope -eq 'LocalMachine') {
            Write-Warning 'Le scope LocalMachine permet le déchiffrement par tout compte ayant accès au fichier. Restreindre les ACL du fichier.'
        }
    }
}


