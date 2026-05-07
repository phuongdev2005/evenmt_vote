@echo off
chcp 65001 >nul
cd /d "%~dp0"
docker run --rm --network host -v ../vote:/app/vote:ro -v ./vote_cookies.sqlite3:/app/vote_cookies.sqlite3 -v ./smsaccount.txt:/app/smsaccount.txt sms_tool python vote.py %*
pause
