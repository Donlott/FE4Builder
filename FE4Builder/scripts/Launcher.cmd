@echo off
setlocal
cd /d "%~dp0.."
python "src\FE4Builder.py"
if errorlevel 1 pause
