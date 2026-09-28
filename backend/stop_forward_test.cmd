@echo off
rem Stop the forward-test recorder started by start_forward_test.cmd
if not exist forward_test.pid (
    echo No forward-test pid on record.
    exit /b 0
)
set /p PID=<forward_test.pid
taskkill /f /pid %PID% >nul 2>&1 && echo Stopped PID %PID% || echo PID %PID% already gone
taskkill /f /im python.exe /fi "WINDOWTITLE eq *forward_test*" >nul 2>&1
rem Plan B: kill any python still running the recorder (venv redirector can
rem leave its base interpreter running when only the wrapper pid is killed).
powershell -NoProfile -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*forward_test*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue; Write-Host ('Killed stray PID ' + $_.ProcessId) }" 2>nul
del forward_test.pid 2>nul
echo Done.