$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

$pidFile = Join-Path $PSScriptRoot "forward_test.pid"
if (Test-Path $pidFile) {
    $old = (Get-Content $pidFile | Select-Object -First 1).Trim()
    if ($old -and (Get-Process -Id $old -ErrorAction SilentlyContinue)) {
        Write-Host "Already running (PID $old). Stop via stop_forward_test.cmd"
        exit 1
    }
    Remove-Item $pidFile -ErrorAction SilentlyContinue
}

$runner = Join-Path $PSScriptRoot "_ft_runner.cmd"
$cmd = 'cmd /c ""' + $runner + '""'
$r = Invoke-CimMethod -ClassName Win32_Process -MethodName Create -Arguments @{
    CommandLine      = $cmd
    CurrentDirectory = $PSScriptRoot
}
if ($r.ReturnValue -ne 0) {
    throw "WMI launch failed rc=$($r.ReturnValue)"
}
Set-Content $pidFile "$($r.ProcessId)"
Write-Host "Forward test started (PID $($r.ProcessId)). Record: forward_log.jsonl. Stop: stop_forward_test.cmd"