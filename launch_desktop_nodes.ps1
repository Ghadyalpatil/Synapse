# SYNAPSE - Launch Two Nodes in Desktop PowerShell Windows
$workspace = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  SYNAPSE TACTICAL MESH: Desktop Multi-Window Launcher" -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Cyan

Write-Host "`n[1/2] Spawning SYNAPSE Node 001 window..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$workspace\start_node1.ps1`""

Start-Sleep -Seconds 1

Write-Host "[2/2] Spawning SYNAPSE Node 002 window..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-ExecutionPolicy", "Bypass", "-File", "`"$workspace\start_node2.ps1`""

Write-Host "`n[SUCCESS] Both nodes launched in separate desktop PowerShell windows!" -ForegroundColor Green
Write-Host "To test message transmission between them, run:" -ForegroundColor Cyan
Write-Host "  python test_local_comms.py" -ForegroundColor White
Write-Host "Or send a message using the CLI:" -ForegroundColor Cyan
Write-Host "  python cli.py --api http://127.0.0.1:8080 send --target SYNAPSE-002 --message `"Host breach at Sector 4B`"" -ForegroundColor White
