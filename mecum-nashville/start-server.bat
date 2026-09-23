@echo off
cd /d "%~dp0"
echo Starting the Nashville block sheet server. Leave this window open.
python serve.py
pause
