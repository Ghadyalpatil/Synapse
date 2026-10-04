@echo off
title SYNAPSE Demonstration Launcher
cd /d "%~dp0"
echo ============================================================
echo   SYNAPSE SURVEILLANCE ^& COMMAND CENTRE DEMONSTRATION
echo   Mode: AIR-GAPPED / ZERO-CLOUD / INDEPENDENT TCP MESH
echo ============================================================
echo.
echo [1/3] Starting SYNAPSE Edge Node 001...
start "SYNAPSE Node 001" cmd /k run_node1.bat

timeout /t 1 /nobreak >nul

echo [2/3] Starting SYNAPSE Edge Node 002...
start "SYNAPSE Node 002" cmd /k run_node2.bat

timeout /t 1 /nobreak >nul

echo [3/3] Starting SYNAPSE Tactical Command Centre...
start "SYNAPSE Command Centre" cmd /k run_command_center.bat

echo.
echo [SUCCESS] Demonstration nodes launched!
echo The Command Centre dashboard will open at: http://127.0.0.1:9000
pause
