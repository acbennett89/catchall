@echo off
rem Double-click: downloads the current season's new games and AP/CFP polls from ESPN,
rem rebuilds the ratings, then opens them in your browser.
setlocal
rem Runs from this folder whatever the current directory is.
cd /d "%~dp0"
set PYTHONUTF8=1
where py >nul 2>nul
if %errorlevel%==0 (set "PY=py -3") else (set "PY=python")
%PY% --version >nul 2>nul || (echo Python 3.8 or newer is needed: https://www.python.org/downloads/ & pause & exit /b 1)
%PY% launch.py --update %*
if errorlevel 1 pause
