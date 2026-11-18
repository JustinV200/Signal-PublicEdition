<#
.SYNOPSIS
Removes this checkout's console logon task and Start-menu shortcut, and stops its server (no admin needed).

.DESCRIPTION
Undoes register.ps1 for one port: stops this checkout's console server on that port
(the logon task's, or one `console open` started), deletes the task and the shortcut
named "Signal console (<folder>, port <port>)". The console's .state folder is kept.
Each part that isn't there is skipped, so it's safe to run again. The naming and the
"is this checkout's" rule are in registration.ps1, shared with register.ps1.

.PARAMETER Port
The port the console was registered on (default 8790).

.EXAMPLE
.\tools\console\unregister.ps1 -WhatIf
.\tools\console\unregister.ps1 -Port 8791
#>
[CmdletBinding(SupportsShouldProcess)]
param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8790
)
$ErrorActionPreference = 'Stop'

. (Join-Path $PSScriptRoot 'registration.ps1')
$name = Get-RegistrationName $Port

if (-not $PSCmdlet.ShouldProcess("$name (task, shortcut and server)", 'Stop and remove')) { return }

$done = @(Remove-ConsoleRegistration $Port)
if ($done) {
    Write-Host "'$name': $($done -join ', ')."
} else {
    Write-Host "Nothing to remove for '$name'."
}
