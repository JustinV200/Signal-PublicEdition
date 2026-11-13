# Signal setup (Windows). Checks for uv, then runs the setup CLI in tools/setup.
#   .\setup.ps1              the setup window: the wizard in the Signal console (resumes)
#   .\setup.ps1 --no-ui      the full setup in this terminal instead
#   .\setup.ps1 ui <tool>    the window, opened at one tool
#   .\setup.ps1 <tool>       set up or redo one tool in this terminal
#   .\setup.ps1 tour         the guided tour
#   .\setup.ps1 status       what's set up
$ErrorActionPreference = 'Stop'
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host 'Signal needs uv first. Install it with:'
    Write-Host '  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"'
    Write-Host 'then open a new terminal and run .\setup.ps1 again.'
    exit 1
}
Set-Location $PSScriptRoot
uv run --project tools/setup --frozen --quiet setup @args
exit $LASTEXITCODE
