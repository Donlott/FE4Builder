@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 goto failed
if not exist ".venv\Scripts\python.exe" goto missing
".venv\Scripts\python.exe" "fe4_modding_studio\studio.py"
if errorlevel 1 goto failed
popd
exit /b 0
:missing
echo Run Setup Windows.bat once before starting the editor.
pause
popd
exit /b 1
:failed
echo.
echo The editor could not run. Copy the error above when reporting the issue.
pause
popd
exit /b 1
