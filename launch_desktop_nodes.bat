@echo off
cd /d "%~dp0"
echo ============================================================
echo   Launching SYNAPSE Node 1 and Node 2 in PowerShell Windows
echo ============================================================
start "SYNAPSE Node 001" powershell -NoExit -ExecutionPolicy Bypass -File "%~dp0start_node1.ps1"
ping 127.0.0.1 -n 3 >nul
start "SYNAPSE Node 002" powershell -NoExit -ExecutionPolicy Bypass -File "%~dp0start_node2.ps1"
echo.
echo Both nodes launched!
echo To test communication, run test_send_message.bat or:
echo   python test_local_comms.py
echo.
