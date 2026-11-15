@echo off
REM Run the F&O dashboard on this laptop: download NSE files, build, and open the site.
REM First time: pip install -r requirements.txt   then:  run_local.bat 400   (backfills ~400 days)
cd /d "%~dp0"
set DAYS=%1
if "%DAYS%"=="" set DAYS=10
python pipeline\fetch_nse.py --days %DAYS%
python pipeline\build.py
start "" http://localhost:8765/
python -m http.server 8765 --directory site
