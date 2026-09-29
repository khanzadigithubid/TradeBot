@echo off
rem Runner for the forward-test recorder. Launched detached via
rem _run_forward_test.ps1 (WMI) so it survives shell/agent death. Console
rem output goes to backend\forward_test.log ; records to forward_log.jsonl.
cd /d "%~dp0"
"%~dp0venv\Scripts\python.exe" -u tools\forward_test.py --out forward_log.jsonl >> forward_test.log 2>&1