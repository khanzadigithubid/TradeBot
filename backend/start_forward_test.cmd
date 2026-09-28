@echo off
rem Start the forward-test recorder detached, TESTNET orders, 15m cadence.
rem Records append to backend\forward_log.jsonl ; console to backend\forward_test.log
if exist forward_test.pid (
    set /p PID=<forward_test.pid
    tasklist /fi "PID eq %PID%" 2>nul | find "%PID%" >nul && (
        echo Already running ^(PID %PID%^). Stop via stop_forward_test.cmd
        exit /b 1
    )
    del forward_test.pid
)
start "TradingBotForwardTest" /min cmd /c ""%CD%\venv\Scripts\python.exe" -u tools\forward_test.py --out forward_log.jsonl >> forward_test.log 2>&1"
powershell -NoProfile -Command "$p = Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { $_.CommandLine -like '*forward_test.py*' } | Select-Object -First 1; if ($p) { $p.ProcessId }" > forward_test.pid
set /p PID=<forward_test.pid
echo Forward test started ^(PID %PID%^). Log: forward_test.log; record: forward_log.jsonl