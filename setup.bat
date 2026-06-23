@echo off
REM local-caption setup (Windows). macOS/Linux: run `bash setup.sh`.
cd /d "%~dp0"
python setup.py %*
