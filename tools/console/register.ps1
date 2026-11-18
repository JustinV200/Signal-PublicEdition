<#
.SYNOPSIS
Starts this checkout's console server at every logon and adds a Start-menu shortcut (no admin needed).

.DESCRIPTION
Creates or replaces two things, both named after this checkout's folder and the port
("Signal console (<folder>, port <port>)"), so a second checkout's registration never
replaces this one's:
  - a per-user logon task that runs
    `uvw run --project tools\console --frozen --no-sync pythonw -m signal_console serve --port <port>`
    from the repo root, as the current user, not elevated, with no console window and no
    time limit. A server that can't start (say the port is taken) exits 1 after writing
    why to tools\console\.state\server.log; the exit code shows as the task's last result.
  - a Start-menu shortcut that runs `... pythonw -m signal_console open --port <port>`.
Setup runs this as the console's optional logon step. Nothing starts now: the task runs at
the next logon. Undo with unregister.ps1 (same -Port).

One checkout has one registration: when this checkout is registered on another port
(after `setup --port N` and running the step again), that registration's task and
shortcut are deleted. Its running server is left alone, since it may be serving the setup
wizard that runs this step; it ends when closed or at logoff, and from the next logon only
the new port's server starts. Two task servers of one checkout would share its .state
folder, and the second to start would strand the first.

It refuses when another program, such as another checkout's console, listens on the port,
and when a task or shortcut of the same name opens another checkout's console. With --no-sync a run
never installs anything, so it also refuses when the console's venv isn't synced. The
naming and the "is this checkout's" rule are in registration.ps1, shared with unregister.ps1.

.PARAMETER Port
The console's port (default 8790). Each checkout's console needs its own.

.EXAMPLE
.\tools\console\register.ps1 -WhatIf
.\tools\console\register.ps1 -Port 8791
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8790
)
$ErrorActionPreference = 'Stop'

# Task Scheduler's restart-on-failure: this many tries, this many minutes apart. Which
# failures count is Task Scheduler's call (a launch failure does; a non-zero exit may not).
$restartCount = 3
$restartIntervalMinutes = 1

. (Join-Path $PSScriptRoot 'registration.ps1')
$name = Get-RegistrationName $Port
$shortcutPath = Get-ShortcutPath $Port
$venv = Join-Path $toolRoot '.venv'
$runArgs = "run --project `"$toolRoot`" --frozen --no-sync pythonw -m signal_console"

# Load the modules the checks below use with -WhatIf off: autoloading them under -WhatIf
# prints stray "What if: New Alias" lines (Import-Module has no -WhatIf of its own).
$whatIf = $WhatIfPreference
$WhatIfPreference = $false
Import-Module NetTCPIP, CimCmdlets, ScheduledTasks
$WhatIfPreference = $whatIf

# Who holds the port, in words: another checkout's console (the folder before the
# tools\console\.venv its launcher runs from), else the program and its pid.
function Get-HolderWords($processes, [int]$processId) {
    foreach ($process in $processes) {
        if ($process.ExecutablePath -match '^(.+)\\tools\\console\\\.venv\\') {
            return "another checkout's console, $($Matches[1])"
        }
    }
    $program = @($processes | ForEach-Object { $_.Name })[0]
    if (-not $program) { $program = 'another program' }
    return "$program (pid $processId)"
}

# Refuse a port another program listens on. Read-only: the socket table and the holder's
# paths, never a connection, so no key or token goes to it. uv's venv launcher starts the
# base Python as a child, so the venv path may be on the listener's parent.
$listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue |
    Where-Object { $_.LocalAddress -in '127.0.0.1', '0.0.0.0', '::' } | Select-Object -First 1
if ($listener) {
    $holder = Get-CimInstance Win32_Process -Filter "ProcessId = $($listener.OwningProcess)"
    $parent = if ($holder) { Get-CimInstance Win32_Process -Filter "ProcessId = $($holder.ParentProcessId)" }
    $chain = @($holder, $parent) | Where-Object { $_ }
    $isOurs = $chain | Where-Object {
        (Test-Contains $_.ExecutablePath "$venv\") -or (Test-Contains $_.CommandLine "$venv\")
    }
    if (-not $isOurs) {
        $what = Get-HolderWords $chain $listener.OwningProcess
        throw "Port $Port is held by $what. Stop it, or register this console on another port: run .\setup.cmd --port <a free port>, then run the console's logon step again."
    }
}

# Refuse to replace a same-named task that runs another checkout's console (same folder name).
$existing = Get-ScheduledTask -TaskName $name -TaskPath '\' -ErrorAction SilentlyContinue
if ($existing -and -not (Test-OwnTask $existing)) {
    throw "The task '$name' runs another checkout's console. Remove it there with its unregister.ps1, or register this one on another port."
}
# The same for a same-named shortcut: never overwrite another checkout's.
if ((Test-Path -LiteralPath $shortcutPath) -and -not (Test-OwnShortcut $shortcutPath)) {
    throw "The shortcut '$shortcutPath' opens another checkout's console. Remove it there with its unregister.ps1, or register this one on another port."
}

# This checkout's registrations on other ports, replaced below (read-only here, so
# -WhatIf names them and changes nothing).
$otherPorts = @(Get-OtherOwnPorts $Port)
$target = "$name (logon task and Start-menu shortcut)"
if ($otherPorts) { $target += ", replacing this checkout's registration on port $($otherPorts -join ', ')" }

if ($PSCmdlet.ShouldProcess($target, 'Register')) {
    # Without a synced venv every run fails with no window to show it. -I imports from
    # the venv, not from a folder in the current directory. 'Continue' because Windows
    # PowerShell can turn a native command's stderr into terminating errors.
    $uvw = (Get-Command uvw.exe).Source
    $uv = (Get-Command uv.exe).Source
    $ErrorActionPreference = 'Continue'
    & $uv run --project $toolRoot --frozen --no-sync python -I -c 'import signal_console.cli'
    $isSynced = $LASTEXITCODE -eq 0
    $ErrorActionPreference = 'Stop'
    if (-not $isSynced) {
        throw "The console's venv isn't synced, so every run would fail. Run '.\setup.cmd console', then register again."
    }

    # -KeepServer: the old port's server may be the one serving the setup wizard that runs
    # this step, so it keeps running. An interactive-logon task's processes end at logoff,
    # so the old and the new task's servers never both run.
    foreach ($oldPort in $otherPorts) {
        $done = @(Remove-ConsoleRegistration $oldPort -KeepServer)
        Write-Host "Replaced this checkout's registration on port ${oldPort}: $($done -join ', ')."
        if (Get-ConsoleServerProcesses $oldPort) {
            Write-Host "This checkout's console still runs on port $oldPort until you close it or log off; from your next logon it starts on port $Port."
        }
    }

    $action = New-ScheduledTaskAction -Execute $uvw -Argument "$runArgs serve --port $Port" `
        -WorkingDirectory $repoRoot
    $user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
    $trigger = New-ScheduledTaskTrigger -AtLogOn -User $user
    # Interactive + Limited: only while the owner is logged on, never elevated.
    $principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
    # IgnoreNew: a second start can't run a second server (it couldn't bind anyway).
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew `
        -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
        -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -RestartCount $restartCount -RestartInterval (New-TimeSpan -Minutes $restartIntervalMinutes)
    Register-ScheduledTask -TaskName $name -TaskPath '\' -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings -Force `
        -Description "Signal: this checkout's console server on port $Port ($toolRoot)." | Out-Null

    $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $uvw
    $shortcut.Arguments = "$runArgs open --port $Port"
    $shortcut.WorkingDirectory = $repoRoot
    $shortcut.Description = "Open this checkout's Signal console (port $Port)."
    $shortcut.Save()

    Write-Host "Registered '$name': the server starts at your next logon. Start-menu shortcut: $shortcutPath"
    Write-Host "Server log: $toolRoot\.state\server.log"
}
