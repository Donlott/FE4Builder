@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 goto failed
where py >nul 2>&1
if errorlevel 1 goto trypython
py -3 setup_windows.py
goto result
:trypython
where python >nul 2>&1
if errorlevel 1 goto missing
python setup_windows.py
:result
if errorlevel 1 goto failed
echo.
echo Setup complete. You can now open Start Studio.bat.
pause
popd
exit /b 0
:missing
echo Python was not found. Install Python with Tcl/Tk and pip from python.org.
echo Enable the Python launcher or Add Python to PATH, then run setup again.
:failed
echo.
echo Setup did not finish. See the error above and README_WINDOWS.txt.
pause
popd
exit /b 1
