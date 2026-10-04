@echo off
title SYNAPSE Command Centre (TCP 5050 / Web 9000)
cd /d "%~dp0"
echo ============================================================
echo   STARTING SYNAPSE COMMAND & CONTROL CENTRE
echo   TCP Comm Port: 5050 ^| Web Console: http://127.0.0.1:9000
echo ============================================================
python command_center.py --node-id COMMAND-CENTER --comm-port 5050 --discovery-port 5997 --port 9000 --broadcast-ip 127.0.0.255 --peer SYNAPSE-001@127.0.0.1:5000 --peer SYNAPSE-002@127.0.0.1:5001 --db-path var/data/command_center.db --keys-dir var/keys/command_center --open-browser --log-level INFO
pause
