@echo off
title SYNAPSE Node 001 (Port 5000 / API 8080)
cd /d "%~dp0"
echo ============================================================
echo   STARTING SYNAPSE NODE 001
echo   Comm Port: 5000 ^| Discovery: 5999 ^| API: 8080
echo ============================================================
python -m synapse --node-id SYNAPSE-001 --comm-port 5000 --discovery-port 5999 --api-port 8080 --broadcast-ip 127.0.0.255 --peer SYNAPSE-002@127.0.0.1:5001 --db-path var/data/node001.db --keys-dir var/keys/node001 --log-level INFO
pause
