# Synapse Mesh Network

A peer-to-peer decentralized mesh communication engine featuring peer discovery (Zeroconf/mDNS), end-to-end encrypted packet delivery, SQLite sync, and a real-time Network Operations Center (NOC) dashboard.

---

## Running the Backend (All 4 Nodes)

The backend network consists of 4 nodes (`A`, `B`, `C`, and `D`). Each node runs on a dedicated socket port and WebSocket port.

### Option 1: Batch Script (Recommended for Windows)

Run the included [`start_nodes.bat`](./start_nodes.bat) from the project root:

```cmd
start_nodes.bat
```

This launches all 4 nodes in separate Command Prompt windows with a 1-second delay between each.

---

### Option 2: Single-Line CMD Command

To launch all 4 nodes simultaneously in separate CMD windows from a single command:

```cmd
start "Node A" cmd /k "python -m backend.main --node-id A --port 9001" & start "Node B" cmd /k "python -m backend.main --node-id B --port 9002" & start "Node C" cmd /k "python -m backend.main --node-id C --port 9003" & start "Node D" cmd /k "python -m backend.main --node-id D --port 9004"
```

---

### Option 3: Individual CMD Commands

If you prefer to start nodes manually across separate terminal windows or tabs:

* **Node A (Port 9001):**
  ```cmd
  python -m backend.main --node-id A --port 9001
  ```
* **Node B (Port 9002):**
  ```cmd
  python -m backend.main --node-id B --port 9002
  ```
* **Node C (Port 9003):**
  ```cmd
  python -m backend.main --node-id C --port 9003
  ```
* **Node D (Port 9004):**
  ```cmd
  python -m backend.main --node-id D --port 9004
  ```

---

### Option 4: PowerShell One-Liner

If running inside PowerShell:

```powershell
@("A 9001", "B 9002", "C 9003", "D 9004") | ForEach-Object { $id, $p = $_.Split(" "); Start-Process cmd -ArgumentList "/k python -m backend.main --node-id $id --port $p" }
```

---

## Node Port Allocation

| Node ID | TCP/Socket Port | WebSocket Port | API Port |
| :---: | :---: | :---: | :---: |
| **Node A** | 9001 | 10001 | 8000 |
| **Node B** | 9002 | 10002 | 8000 |
| **Node C** | 9003 | 10003 | 8000 |
| **Node D** | 9004 | 10004 | 8000 |

> *Note: WebSocket port is computed dynamically as `NODE_PORT + 1000`.*

---

## Frontend Dashboard

The frontend NOC dashboard is located in [`frontend/`](./frontend).

1. Navigate to the frontend directory:
   ```cmd
   cd frontend
   ```
2. Install dependencies:
   ```cmd
   npm install
   ```
3. Start the Vite development server:
   ```cmd
   npm run dev
   ```

---

## Running Tests & Benchmarks

* **Unit Tests:**
  ```cmd
  pytest tests/test_mesh.py
  ```
* **Benchmark Harness:**
  ```cmd
  python benchkit/harness.py
  ```
