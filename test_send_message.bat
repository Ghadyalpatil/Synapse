@echo off
title SYNAPSE Test Comms
cd /d "%~dp0"
echo ============================================================
echo   RUNNING SYNAPSE TWO-NODE MESSAGE TRANSMISSION TEST
echo ============================================================
python test_local_comms.py
echo.
pause
