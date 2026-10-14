@echo off
echo Starting 4 Mesh Network Nodes...

start "Node A (Port 9001)" cmd /k "python -m backend.main --node-id A --port 9001"
timeout /t 1 /nobreak >nul

start "Node B (Port 9002)" cmd /k "python -m backend.main --node-id B --port 9002"
timeout /t 1 /nobreak >nul

start "Node C (Port 9003)" cmd /k "python -m backend.main --node-id C --port 9003"
timeout /t 1 /nobreak >nul

start "Node D (Port 9004)" cmd /k "python -m backend.main --node-id D --port 9004"

echo All 4 nodes launched in separate windows.
