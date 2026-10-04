$Host.UI.RawUI.WindowTitle = "SYNAPSE Node 001 (Port 5000 / API 8080)"
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  LAUNCHING SYNAPSE NODE 001" -ForegroundColor Green
Write-Host "  TCP Comm: 5000 | Discovery: 5999 | API: 8080" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan
Set-Location -Path $PSScriptRoot
python -m synapse --node-id SYNAPSE-001 --comm-port 5000 --discovery-port 5999 --api-port 8080 --broadcast-ip 127.0.0.255 --peer SYNAPSE-002@127.0.0.1:5001 --peer COMMAND-CENTER@127.0.0.1:5050 --auto-poll 2.5 --stream-telemetry --db-path var/data/node001.db --keys-dir var/keys/node001 --log-level INFO
