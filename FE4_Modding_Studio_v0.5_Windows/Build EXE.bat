@echo off
setlocal
pushd "%~dp0"
if errorlevel 1 goto failed
if not exist ".venv\Scripts\python.exe" goto missing
".venv\Scripts\python.exe" -m pip install "pyinstaller>=6.16,<7"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --windowed --name FE4_Modding_Studio --add-data "fe4_modding_studio\data:data" --add-data "fe4_modding_studio\slot_names.json:." "fe4_modding_studio\studio.py"
if errorlevel 1 goto failed
echo.
echo Built dist\FE4_Modding_Studio\FE4_Modding_Studio.exe
echo Test the app, then share the ENTIRE dist\FE4_Modding_Studio folder.
echo That folder includes the runtime; the recipient does not need Python.
pause
popd
exit /b 0
:missing
echo Run Setup Windows.bat first.
:failed
echo Build failed. See the error above.
pause
popd
exit /b 1
