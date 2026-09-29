@echo off
rem Start the forward-test recorder fully detached (WMI parent, survives shell
rem or agent death). TESTNET orders, 15m cadence, 20 symbols. Records append
rem to backend\forward_log.jsonl. Requires an already-provisioned Binance
rem testnet API key (normal binance_* .env settings work, with TESTNET=true).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0_run_forward_test.ps1"