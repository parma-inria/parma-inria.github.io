@echo off
setlocal
REM Run from the project folder, even when this file is opened elsewhere.
cd /d "%~dp0"

REM Prefer the Windows Python launcher, with Python 3.10 or later.
py -3 -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if errorlevel 1 goto try_python
py -3 tools\preview.py --open
goto done

:try_python
REM Fall back to Python available on PATH.
python -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if errorlevel 1 goto missing_python
python tools\preview.py --open
goto done

:missing_python
REM Explain what is missing and leave the message visible.
echo Python 3.10 or later is required. Install Python and try again.
pause
exit /b 1

:done
REM Keep the terminal open if the preview could not start.
if errorlevel 1 pause
