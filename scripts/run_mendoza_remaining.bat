@echo off
cd /d "c:\Users\gusta\review-leads"
set PYTHONPATH=c:\Users\gusta\review-leads
set PYTHONIOENCODING=utf-8
if not exist "data\exports" mkdir "data\exports"
echo ===== START %date% %time% =====>> "data\exports\mendoza-wa-scheduled.log"
".venv\Scripts\python.exe" "scripts\send_mendoza_batches.py" --remaining-all --batch-size 10 >> "data\exports\mendoza-wa-scheduled.log" 2>&1
echo EXIT_CODE=%ERRORLEVEL% >> "data\exports\mendoza-wa-scheduled.log"
echo ===== END %date% %time% =====>> "data\exports\mendoza-wa-scheduled.log"
