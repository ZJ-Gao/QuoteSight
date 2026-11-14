@echo off
rem Windows: double-click to update the index and open the board. Close this window to stop.
cd /d "%~dp0"
.venv\Scripts\quotesight.exe update
.venv\Scripts\quotesight-app.exe
pause
