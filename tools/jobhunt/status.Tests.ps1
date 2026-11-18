# status.Tests.ps1: Pester 3 tests for status.ps1 (tools/jobhunt), on fixture logs in TestDrive.
#
#   powershell -NoProfile -Command "Invoke-Pester tools\jobhunt\status.Tests.ps1"

$script = Join-Path $PSScriptRoot 'status.ps1'
$runScript = Join-Path $PSScriptRoot 'run.ps1'

# Log bodies in run.ps1's wording (the last It checks run.ps1 still writes it).
$started = "2026-11-17T08:00:01 claude: C:\bin\claude.exe`n2026-11-17T08:00:01 args: -p go"
$logs = @{
    dryRun = "$started`n2026-11-17T08:00:01 dry run: not starting claude"
    lockHeld = '2026-11-17T08:00:01 lock held by another run; exiting (in use)'
    ok = "$started`n2026-11-17T09:00:00 run ended with code 0"
    failed = "$started`n2026-11-17T09:00:00 run ended with code 1"
    noClaude = '2026-11-17T08:00:01 claude executable not found (PATH); exiting'
    going = $started
}

function Invoke-Status([hashtable]$Files, [int]$AgeHours = 0) {
    # Writes the fixture logs (name -> body, aged by AgeHours) to a fresh folder and
    # runs status.ps1 on it. Returns 'exit|words'.
    $dir = Join-Path $TestDrive ([guid]::NewGuid())
    New-Item -ItemType Directory $dir | Out-Null
    foreach ($name in $Files.Keys) {
        $path = Join-Path $dir $name
        Set-Content $path $Files[$name] -Encoding utf8
        (Get-Item $path).LastWriteTime = (Get-Date).AddHours(-$AgeHours)
    }
    $line = & $script -LogDir $dir | Select-Object -Last 1
    return "$LASTEXITCODE|$(($line | ConvertFrom-Json).words)"
}

Describe 'status.ps1' {
    $older = '2026-11-16-080001.log'
    $newer = '2026-11-17-080001.log'
    $cases = @(
        @{ name = 'passes over a newer dry run and lock-held start'; files = @{ $older = $logs.ok; $newer = $logs.dryRun; '2026-11-17-090001.log' = $logs.lockHeld }
            expected = '0|last run finished (2026-11-16 08:00)' },
        @{ name = 'reads a failed run as down'; files = @{ $newer = $logs.failed }
            expected = '1|the last run (2026-11-17 08:00) ended with code 1' },
        @{ name = "reads a run that couldn't start as down"; files = @{ $newer = $logs.noClaude }
            expected = "1|the last run (2026-11-17 08:00) couldn't start" },
        @{ name = 'reads an old log with no end line as stopped'; files = @{ $newer = $logs.going }; age = 5
            expected = '1|the last run (2026-11-17 08:00) stopped without finishing' },
        @{ name = 'reads a recent log with no end line as going'; files = @{ $newer = $logs.going }
            expected = '0|a run is going (started 2026-11-17 08:00)' },
        @{ name = 'passes with no logs'; files = @{}; expected = '0|set up, no run yet' }
    )
    foreach ($case in $cases) {
        It $case.name {
            Invoke-Status $case.files ([int]$case.age) | Should Be $case.expected
        }
    }

    It 'matches the lines run.ps1 writes' {
        $source = Get-Content $runScript -Raw
        foreach ($text in @('dry run: not starting claude', 'lock held by another run',
                'claude executable not found', "couldn't open the lock file", 'run ended with code')) {
            $source.Contains($text) | Should Be $true
        }
    }
}
