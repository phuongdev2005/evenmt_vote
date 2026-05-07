@echo off
chcp 65001 >nul
cd /d "%~dp0"
docker run --rm --network host -v ../vote:/app/vote:ro -v ./vote_cookies.sqlite3:/app/vote_cookies.sqlite3 -v ./smsaccount.txt:/app/smsaccount.txt -v ./failed_sms.txt:/app/failed_sms.txt -v ./results_sms.txt:/app/results_sms.txt sms_tool python main.py %*
pause
