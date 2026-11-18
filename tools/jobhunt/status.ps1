# status.ps1: the setup tool's health check for the job runner (tools/jobhunt).
#
# Reads the newest real run's log in .logs/ and prints one JSON line
# {words, fix, command} (tools/setup/README.md, "Verify checks"). Read-only:
# it never takes run.ps1's lock, writes a log or starts a run. Dry runs and runs
# that found the lock held are passed over, since neither is a real run.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\jobhunt\status.ps1 [-LogDir <dir>]
#
# -LogDir reads another folder (the tests use fixture logs); the default is .logs/.
# Exit codes: 0 no run yet, a run going, or the last run ended with code 0;
# 1 the last run failed.

param([string]$LogDir = (Join-Path $PSScriptRoot '.logs'))

$ErrorActionPreference = 'Stop'

# run.ps1's log lines this reads (keep in step with run.ps1; status.Tests.ps1 checks
# that run.ps1 still writes each of them).
$SkipPatterns = @('dry run: not starting claude', 'lock held by another run')
$StartFailPatterns = @('claude executable not found', "couldn't open the lock file")
$EndPattern = 'run ended with code (-?\d+)'
# Past the scheduled task's 3 h 50 min limit, a log with no end line is a run that was killed.
$MaxRunHours = 4

function Write-Summary([string]$Words, [string]$Fix) {
    # One compressed JSON line; [ordered] keeps the keys in contract order.
    $summary = [ordered]@{ words = $Words; fix = $(if ($Fix) { $Fix } else { $null }); command = $null }
    Write-Output ($summary | ConvertTo-Json -Compress)
}

function Read-Log([string]$Path) {
    # ReadWrite sharing: run.ps1 may be appending to the newest log right now.
    $stream = [System.IO.FileStream]::new($Path, 'Open', 'Read', 'ReadWrite')
    try {
        $reader = [System.IO.StreamReader]::new($stream)
        return $reader.ReadToEnd()
    } finally {
        $stream.Dispose()
    }
}

function Get-RunTime([string]$Name) {
    # 2026-11-17-120001.log -> 2026-11-17 12:00
    if ($Name -match '^(\d{4}-\d{2}-\d{2})-(\d{2})(\d{2})') { return "$($Matches[1]) $($Matches[2]):$($Matches[3])" }
    return $Name
}

$logs = @()
if (Test-Path $LogDir) {
    # Names are timestamps, so a reverse name sort is newest first.
    $logs = @(Get-ChildItem $LogDir -File -Filter '*.log' | Sort-Object Name -Descending)
}
foreach ($log in $logs) {
    $text = Read-Log $log.FullName
    if ($SkipPatterns | Where-Object { $text.Contains($_) }) { continue }
    $when = Get-RunTime $log.Name
    $fix = "See tools/jobhunt/.logs/$($log.Name)."
    if ($StartFailPatterns | Where-Object { $text.Contains($_) }) {
        Write-Summary "the last run ($when) couldn't start" $fix
        exit 1
    }
    if ($text -match $EndPattern) {
        $code = [int]$Matches[1]
        if ($code -eq 0) { Write-Summary "last run finished ($when)" $null; exit 0 }
        Write-Summary "the last run ($when) ended with code $code" $fix
        exit 1
    }
    # No end line: run.ps1 writes it when the run stops, unless the run was killed.
    if ($log.LastWriteTime -lt (Get-Date).AddHours(-$MaxRunHours)) {
        Write-Summary "the last run ($when) stopped without finishing" $fix
        exit 1
    }
    Write-Summary "a run is going (started $when)" $null
    exit 0
}
Write-Summary 'set up, no run yet' 'It runs on its schedule once the schedule step is done.'
exit 0
