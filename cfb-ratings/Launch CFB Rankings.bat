@echo off
rem Double-click: opens the FBS Efficiency Ratings in your browser.
rem Leave the window open while you use the site; close it to stop the local server.
setlocal
rem Runs from this folder whatever the current directory is.
cd /d "%~dp0"
set PYTHONUTF8=1
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% --version >nul 2>nul || (echo Python 3.8 or newer is needed: https://www.python.org/downloads/ & pause & exit /b 1)
%PY% launch.py %*
if errorlevel 1 pause
