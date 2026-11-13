# seed-profile.ps1: copies the main browser profile into the job runner's
# profile so existing sign-ins (Google and others) carry over (tools/jobhunt).
#
# tools/browser/.profile -> .profile-jobs, and .state/cookies.bin ->
# .state/cookies-jobs.bin when it exists. Refuses while any Edge uses either
# profile (a live profile copies half-written). Skips caches and lock files.
# Overwrites what's in .profile-jobs; rerun it to refresh the sign-ins.
#
#   powershell -NoProfile -File tools\jobhunt\seed-profile.ps1

$ErrorActionPreference = 'Stop'

$browserDir = (Resolve-Path (Join-Path $PSScriptRoot '..\browser')).Path
$source = Join-Path $browserDir '.profile'
$target = Join-Path $browserDir '.profile-jobs'
$cookieSource = Join-Path $browserDir '.state\cookies.bin'
$cookieTarget = Join-Path $browserDir '.state\cookies-jobs.bin'
# Caches rebuild themselves; Singleton*/lockfile would make Edge think the copy is in use.
$skipDirs = @('Cache', 'Code Cache', 'GPUCache', 'GrShaderCache', 'GraphiteDawnCache', 'ShaderCache', 'Service Worker', 'CacheStorage', 'Crashpad', 'BrowserMetrics')
$skipFiles = @('Singleton*', 'lockfile', 'LOCK', '*.pma')

function Test-ProfileInUse([string]$ProfileDir) {
    # True if an Edge process was started with this exact --user-data-dir.
    $pattern = '--user-data-dir="?' + [regex]::Escape($ProfileDir) + '("|\s|$)'
    $edges = Get-CimInstance Win32_Process -Filter "Name='msedge.exe'"
    return [bool]($edges | Where-Object { $_.CommandLine -match $pattern })
}

if (-not (Test-Path $source)) { Write-Error "no main profile at $source" }
foreach ($dir in @($source, $target)) {
    if (Test-ProfileInUse $dir) {
        Write-Error "Edge is running on $dir; close that browser (or stop its MCP server) and rerun"
    }
}

# /MIR makes the copy match the source; robocopy exit codes below 8 mean success.
robocopy $source $target /MIR /R:1 /W:1 /NFL /NDL /NJH /NP /XD @skipDirs /XF @skipFiles | Out-Null
if ($LASTEXITCODE -ge 8) { Write-Error "robocopy failed with code $LASTEXITCODE" }

if (Test-Path $cookieSource) {
    Copy-Item $cookieSource $cookieTarget -Force
    Write-Output "copied saved cookies to $cookieTarget"
} else {
    Write-Output "no $cookieSource yet (the main browser writes it on a clean close); skipped"
}
Write-Output "seeded $target from $source"
