$Host.UI.RawUI.WindowTitle = "SYNAPSE Node 002 (Port 5001 / API 8081)"
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  LAUNCHING SYNAPSE NODE 002" -ForegroundColor Green
Write-Host "  TCP Comm: 5001 | Discovery: 5998 | API: 8081" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan
Set-Location -Path $PSScriptRoot
python -m synapse --node-id SYNAPSE-002 --comm-port 5001 --discovery-port 5998 --api-port 8081 --broadcast-ip 127.0.0.255 --peer SYNAPSE-001@127.0.0.1:5000 --peer COMMAND-CENTER@127.0.0.1:5050 --auto-poll 3.0 --stream-telemetry --db-path var/data/node002.db --keys-dir var/keys/node002 --log-level INFO
