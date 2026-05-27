@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
set "VENV_PYTHON=%SCRIPT_DIR%.venv\Scripts\python.exe"

if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" "%SCRIPT_DIR%main.py" %*
    goto :done
)

where python >nul 2>nul
if %errorlevel%==0 (
    python "%SCRIPT_DIR%main.py" %*
    goto :done
)

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 "%SCRIPT_DIR%main.py" %*
    goto :done
)

echo Python was not found on PATH. Install Python 3 and try again.
exit /b 1

:done
set "EXIT_CODE=%errorlevel%"
endlocal & set "EXIT_CODE=%EXIT_CODE%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Portfolio Rebalancer exited with code %EXIT_CODE%.
)

pause