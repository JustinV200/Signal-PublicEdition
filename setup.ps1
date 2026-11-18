# Signal setup (Windows). Checks for uv, then runs the setup CLI in tools/setup.
# Start it through setup.cmd, which gets past PowerShell's script policy:
#   .\setup.cmd              the setup window: the wizard in the Signal console (resumes)
#   .\setup.cmd --no-ui      the full setup in this terminal instead
#   .\setup.cmd ui <tool>    the window, opened at one tool
#   .\setup.cmd <tool>       set up or redo one tool in this terminal
#   .\setup.cmd step <tool> <step>  just that step, nothing else (the window's Open a terminal)
#   .\setup.cmd tour         the guided tour
#   .\setup.cmd status       what's set up
$ErrorActionPreference = 'Stop'
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host 'Signal needs uv first. Install it with:'
    Write-Host '  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
    Write-Host 'then open a new terminal and run .\setup.cmd again.'
    exit 1
}
Set-Location $PSScriptRoot
# The first run is silent for a while (uv may fetch Python and build the venv), so say so.
Write-Host 'Getting setup ready (first run takes a minute)...'
uv run --project tools/setup --frozen --quiet setup @args
exit $LASTEXITCODE
