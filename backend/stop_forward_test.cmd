@echo off
rem Stop the forward-test recorder started by start_forward_test.cmd
if not exist forward_test.pid (
    echo No forward-test pid on record.
    exit /b 0
)
set /p PID=<forward_test.pid
taskkill /f /pid %PID% >nul 2>&1 && echo Stopped PID %PID% || echo PID %PID% already gone
del forward_test.pid 2>nul