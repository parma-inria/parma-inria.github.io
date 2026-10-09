@echo off
setlocal
cd /d "%~dp0"

py -3 -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if errorlevel 1 goto try_python
py -3 tools\preview.py --open
goto done

:try_python
python -c "import sys; assert sys.version_info >= (3, 10)" >nul 2>&1
if errorlevel 1 goto missing_python
python tools\preview.py --open
goto done

:missing_python
echo Python 3.10 or later is required. Install Python and try again.
pause
exit /b 1

:done
if errorlevel 1 pause
