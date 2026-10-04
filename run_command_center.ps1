$Host.UI.RawUI.WindowTitle = "SYNAPSE Command Centre (TCP 5050 / Web 9000)"
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  LAUNCHING SYNAPSE COMMAND & CONTROL CENTRE" -ForegroundColor Green
Write-Host "  TCP Comm Mesh Port: 5050 | Web Console: http://127.0.0.1:9000" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan
Set-Location -Path $PSScriptRoot
python command_center.py --node-id COMMAND-CENTER --comm-port 5050 --discovery-port 5997 --port 9000 --broadcast-ip 127.0.0.255 --peer SYNAPSE-001@127.0.0.1:5000 --peer SYNAPSE-002@127.0.0.1:5001 --db-path var/data/command_center.db --keys-dir var/keys/command_center --open-browser --log-level INFO
