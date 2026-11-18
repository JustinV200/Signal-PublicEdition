@rem Signal setup (Windows): runs setup.ps1 past PowerShell's script policy, which blocks
@rem scripts on a new PC. Type .\setup.cmd [--no-ui | tool | ui tool | step tool step | tour | status], or
@rem double-click it for the setup window. setup.ps1 lists what each form does.
@setlocal
@powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1" %*
@set "SETUP_EXIT=%errorlevel%"
@rem A double-click runs this in its own window, which closes on exit: on a failure, wait so the message can be read.
@if not "%SETUP_EXIT%"=="0" if "%~1"=="" pause
@exit /b %SETUP_EXIT%
