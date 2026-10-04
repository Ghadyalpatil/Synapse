# SYNAPSE TACTICAL MESH: Complete System Demonstration Launcher
# Spawns Node 001, Node 002, and the Command Centre in separate desktop windows.
$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  SYNAPSE SURVEILLANCE & COMMAND CENTRE DEMONSTRATION" -ForegroundColor Green
Write-Host "  Mode: AIR-GAPPED / ZERO-CLOUD / INDEPENDENT TCP MESH" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan

Write-Host "`n[1/3] Spawning SYNAPSE Edge Node 001..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$workspace\start_node1.ps1`""

Start-Sleep -Seconds 1

Write-Host "[2/3] Spawning SYNAPSE Edge Node 002..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$workspace\start_node2.ps1`""

Start-Sleep -Seconds 1

Write-Host "[3/3] Spawning SYNAPSE Tactical Command Centre..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$workspace\run_command_center.ps1`""

Write-Host "`n[SUCCESS] All components operational!" -ForegroundColor Green
Write-Host "  - Node 001:       http://127.0.0.1:8080 (TCP Comm Port: 5000)" -ForegroundColor White
Write-Host "  - Node 002:       http://127.0.0.1:8081 (TCP Comm Port: 5001)" -ForegroundColor White
Write-Host "  - Command Centre: http://127.0.0.1:9000 (TCP Comm Port: 5050)" -ForegroundColor Cyan
Write-Host "`nThe Command Centre dashboard will open automatically in your browser." -ForegroundColor Green
Write-Host "It will display live inputs from thermal, acoustic, and motion sensors" -ForegroundColor White
Write-Host "streamed over the independent SYNAPSE mesh communication system." -ForegroundColor White
