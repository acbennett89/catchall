@echo off
cd /d "%~dp0"
echo Starting the UFC fight analyzer. Leave this window open while you use it.
python serve.py --open
pause
