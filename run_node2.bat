@echo off
title SYNAPSE Node 002 (Port 5001 / API 8081)
cd /d "%~dp0"
echo ============================================================
echo   STARTING SYNAPSE NODE 002
echo   Comm Port: 5001 ^| Discovery: 5998 ^| API: 8081
echo ============================================================
python -m synapse --node-id SYNAPSE-002 --comm-port 5001 --discovery-port 5998 --api-port 8081 --broadcast-ip 127.0.0.255 --peer SYNAPSE-001@127.0.0.1:5000 --db-path var/data/node002.db --keys-dir var/keys/node002 --log-level INFO
pause
