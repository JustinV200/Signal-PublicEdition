# account.ps1: passwords for the dedicated job-site accounts the job runner
# creates (Workday and the like), so a run can sign up and a later run can sign
# back in (tools/jobhunt, used by life/areas/job-search/runbook.md).
#
# Owner decision: these accounts hold nothing but job applications, so a random
# password typed by the runner is fine. Never use this for the owner's real logins.
#
# Passwords are DPAPI-encrypted for the current Windows user in
# .state/accounts.json (gitignored), keyed by site host. Each entry is
# "pending" until the runner confirms the sign-up worked, then "created".
#
#   account.ps1 -Site example.wd5.myworkdayjobs.com -Email you@example.com            # get or make the password
#   account.ps1 -Site example.wd5.myworkdayjobs.com -Email you@example.com -Confirm   # sign-up worked
#
# Prints one JSON line: {"site", "email", "status", "password"}.
# Getting a site with an entry (pending or created) returns its stored password.

param(
    [Parameter(Mandatory = $true)][string]$Site,
    [switch]$Confirm,
    # The application email from profile.md; the runbook always passes it.
    [Parameter(Mandatory = $true)][string]$Email
)

$ErrorActionPreference = 'Stop'

$statePath = Join-Path $PSScriptRoot '.state\accounts.json'
$passwordLength = 20
# Symbols most sign-up forms accept; classes are checked so each one appears.
$lowers = 'abcdefghijkmnopqrstuvwxyz'
$uppers = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
$digits = '23456789'
$symbols = '!@#$%^*-_=+?'

function New-Password {
    # A random password with every character class, from the OS crypto RNG.
    $alphabet = $lowers + $uppers + $digits + $symbols
    # Bytes at or above this limit would bias the modulo, so they are skipped.
    $limit = 256 - (256 % $alphabet.Length)
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $byte = New-Object byte[] 1
    while ($true) {
        $password = ''
        while ($password.Length -lt $passwordLength) {
            $rng.GetBytes($byte)
            if ($byte[0] -lt $limit) { $password += $alphabet[$byte[0] % $alphabet.Length] }
        }
        $hasAll = ($password -cmatch '[a-z]') -and ($password -cmatch '[A-Z]') -and
            ($password -match '[0-9]') -and ($password -match '[^a-zA-Z0-9]')
        if ($hasAll) { return $password }
    }
}

function Read-Accounts {
    # The stored accounts as a hashtable of host -> entry ({} when no file yet).
    $accounts = @{}
    if (Test-Path $statePath) {
        $json = Get-Content -Raw -LiteralPath $statePath | ConvertFrom-Json
        foreach ($property in $json.PSObject.Properties) { $accounts[$property.Name] = $property.Value }
    }
    return $accounts
}

function Save-Accounts($accounts) {
    # Write through a temp file so a crash can't leave half a file.
    New-Item -ItemType Directory -Force (Split-Path $statePath) | Out-Null
    $temp = "$statePath.tmp"
    $text = [pscustomobject]$accounts | ConvertTo-Json -Depth 3
    [System.IO.File]::WriteAllText($temp, $text, (New-Object System.Text.UTF8Encoding $false))
    Move-Item -Force -LiteralPath $temp -Destination $statePath
}

function Unprotect-Password([string]$encrypted) {
    $secure = ConvertTo-SecureString $encrypted
    return (New-Object System.Net.NetworkCredential('', $secure)).Password
}

$siteHost = $Site.Trim().ToLowerInvariant()
if ($siteHost -notmatch '^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$') {
    Write-Error "not a host name: $Site (pass the site's host, like example.wd5.myworkdayjobs.com)"
}

$accounts = Read-Accounts
$entry = $accounts[$siteHost]
if ($Confirm) {
    if (-not $entry) { Write-Error "no account for $siteHost; get its password first" }
    $entry.status = 'created'
    $entry.updated = (Get-Date).ToString('o')
    Save-Accounts $accounts
} elseif (-not $entry) {
    # No DPAPI key argument: ConvertFrom-SecureString encrypts for this Windows user.
    $secure = ConvertTo-SecureString (New-Password) -AsPlainText -Force
    $entry = [pscustomobject]@{
        email = $Email
        status = 'pending'
        password = ConvertFrom-SecureString $secure
        updated = (Get-Date).ToString('o')
    }
    $accounts[$siteHost] = $entry
    Save-Accounts $accounts
}

[pscustomobject]@{
    site = $siteHost
    email = $entry.email
    status = $entry.status
    password = Unprotect-Password $entry.password
} | ConvertTo-Json -Compress
