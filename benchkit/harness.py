import asyncio
import time
import json
import shutil
import os
import sys
import statistics as st
import psutil
import requests
import websockets

# ---------------------------------------------------------------------------
# Place this script's containing folder ("benchkit") as a sibling of your
# "backend" folder, i.e.:
#   mesh-networkTEST3/
#     backend/
#     frontend/
#     benchkit/
#       harness.py   <-- run this with: python harness.py
# It will automatically create 4 isolated run copies (run_A..run_D) under
# benchkit/_run/, each with its own SQLite DB, so the four node processes
# don't contend for a single shared "mesh_network.db" file. Nothing in your
# original backend/ folder is modified.
# ---------------------------------------------------------------------------

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
BACKEND_SRC = os.path.join(PROJECT_ROOT, "backend")
BASE = os.path.join(SCRIPT_DIR, "_run")

NODES = {
    "A": {"port": 9001, "rest": 9501, "ws": 10001},
    "B": {"port": 9002, "rest": 9502, "ws": 10002},
    "C": {"port": 9003, "rest": 9503, "ws": 10003},
    "D": {"port": 9004, "rest": 9504, "ws": 10004},
}
MESSAGES_PER_SCENARIO = 30
DELIVERY_TIMEOUT = 6.0


def setup_run_dirs():
    if not os.path.isdir(BACKEND_SRC):
        print(f"ERROR: could not find 'backend' folder at {BACKEND_SRC}")
        print("Place this benchkit folder as a sibling of your backend/ folder.")
        sys.exit(1)
    os.makedirs(BASE, exist_ok=True)
    for n in NODES:
        rundir = os.path.join(BASE, f"run_{n}")
        dest_backend = os.path.join(rundir, "backend")
        if os.path.isdir(dest_backend):
            shutil.rmtree(dest_backend, ignore_errors=True)
        shutil.copytree(
            BACKEND_SRC, dest_backend,
            ignore=shutil.ignore_patterns("__pycache__", "*.db"),
        )
    print(f"Prepared isolated run directories under {BASE}", flush=True)


results = {
    "discovery": {},         # node_id -> seconds until 3 peers discovered
    "resource_samples": {},  # scenario -> node_id -> list of (cpu%, rss_mb)
    "scenarios": {},         # scenario -> list of {"success":bool,"latency_ms":float}
}

processes = {}
proc_start_time = {}
discovered_counts = {n: set() for n in NODES}
discovery_done_time = {}
log_file_handles = {}
log_file_positions = {n: 0 for n in NODES}


async def discovery_watcher():
    """Periodically scan each node's own log file (written directly by the OS,
    not piped through this process) for 'Discovered Node:' lines, keeping
    memory/IPC overhead low even under heavy print volume from the backend."""
    while True:
        for node_id in NODES:
            path = f"{BASE}/run_{node_id}/node_stdout.log"
            try:
                with open(path, "r", errors="ignore") as f:
                    f.seek(log_file_positions[node_id])
                    new_data = f.read()
                    log_file_positions[node_id] = f.tell()
            except FileNotFoundError:
                continue
            if not new_data:
                continue
            ts = time.time()
            for line in new_data.splitlines():
                if "Discovered Node:" in line:
                    try:
                        peer = line.split("Discovered Node:")[1].strip().split(" ->")[0].strip()
                        discovered_counts[node_id].add(peer)
                        if len(discovered_counts[node_id]) == 3 and node_id not in discovery_done_time:
                            discovery_done_time[node_id] = ts
                    except Exception:
                        pass
        await asyncio.sleep(0.2)


async def start_node(node_id):
    cfg = NODES[node_id]
    rundir = f"{BASE}/run_{node_id}"
    logpath = f"{rundir}/node_stdout.log"
    logf = open(logpath, "wb", buffering=0)
    log_file_handles[node_id] = logf
    proc_start_time[node_id] = time.time()
    child_env = dict(os.environ)
    child_env["PYTHONUNBUFFERED"] = "1"
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-u", "-m", "backend.main",
        "--node-id", node_id, "--port", str(cfg["port"]),
        cwd=rundir,
        stdout=logf,
        stderr=asyncio.subprocess.STDOUT,
        env=child_env,
    )
    processes[node_id] = proc
    return proc


async def kill_node(node_id):
    proc = processes.get(node_id)
    if proc and proc.returncode is None:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=5)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()


pending_deliveries = {}  # packet_id -> asyncio.Future
delivered_log = {}  # packet_id -> delivery timestamp (for events that arrive early)
ws_connection_holder = {}


async def ws_listener_d():
    uri = f"ws://127.0.0.1:{NODES['D']['ws']}"
    for attempt in range(30):
        try:
            ws = await websockets.connect(uri)
            ws_connection_holder["ws"] = ws
            break
        except Exception:
            await asyncio.sleep(0.3)
    else:
        raise RuntimeError("Could not connect to D's websocket")

    ws = ws_connection_holder["ws"]
    async for message in ws:
        ts = time.time()
        try:
            event = json.loads(message)
        except Exception:
            continue
        if event.get("type") == "MESSAGE_DELIVERED":
            pid = event.get("packet_id")
            delivered_log[pid] = ts
            fut = pending_deliveries.get(pid)
            if fut and not fut.done():
                fut.set_result(ts)


async def send_one(node_from, node_to):
    cfg_from = NODES[node_from]
    loop = asyncio.get_event_loop()
    t0 = time.time()
    resp = await loop.run_in_executor(
        None,
        lambda: requests.post(
            f"http://127.0.0.1:{cfg_from['rest']}/send",
            json={"destination": node_to, "payload": f"bench-{t0}"},
            timeout=5,
        ),
    )
    data = resp.json()
    packet_id = data.get("packet_id")
    if not packet_id:
        return {"success": False, "latency_ms": None, "error": data}

    # The delivery event can arrive while we were blocked waiting on the
    # HTTP response above (localhost delivery can be sub-millisecond), so
    # check whether it already showed up before registering a future to
    # wait on -- otherwise a genuinely instant delivery gets misreported
    # as a timeout/failure.
    if packet_id in delivered_log:
        t1 = delivered_log.pop(packet_id)
        return {"success": True, "latency_ms": (t1 - t0) * 1000.0}

    fut = asyncio.get_event_loop().create_future()
    pending_deliveries[packet_id] = fut
    try:
        t1 = await asyncio.wait_for(fut, timeout=DELIVERY_TIMEOUT)
        return {"success": True, "latency_ms": (t1 - t0) * 1000.0}
    except asyncio.TimeoutError:
        return {"success": False, "latency_ms": None}
    finally:
        pending_deliveries.pop(packet_id, None)
        delivered_log.pop(packet_id, None)


async def sample_resources(active_nodes, duration, out_list, interval=0.15):
    pids = {}
    for n in active_nodes:
        proc = processes.get(n)
        if proc and proc.returncode is None:
            try:
                pids[n] = psutil.Process(proc.pid)
                pids[n].cpu_percent(interval=None)  # prime
            except Exception:
                pass
    end_t = time.time() + duration
    while time.time() < end_t:
        for n, p in pids.items():
            try:
                cpu = p.cpu_percent(interval=None)
                mem = p.memory_info().rss / (1024 * 1024)
                out_list.setdefault(n, []).append((cpu, mem))
            except Exception:
                pass
        await asyncio.sleep(interval)


async def run_scenario(name, active_nodes):
    res_samples = {}
    sampler_task = asyncio.create_task(
        sample_resources(active_nodes, duration=MESSAGES_PER_SCENARIO * 0.25 + 2, out_list=res_samples)
    )
    trials = []
    for i in range(MESSAGES_PER_SCENARIO):
        r = await send_one("A", "D")
        trials.append(r)
        await asyncio.sleep(0.1)
    await sampler_task
    results["scenarios"][name] = trials
    results["resource_samples"][name] = res_samples
    succ = sum(1 for t in trials if t["success"])
    lat = [t["latency_ms"] for t in trials if t["success"]]
    print(f"[{name}] success={succ}/{len(trials)} "
          f"mean_latency={ (st.mean(lat) if lat else None) }")


async def main():
    setup_run_dirs()
    print("Starting nodes A, B, C, D ...", flush=True)
    for n in ["A", "B", "C", "D"]:
        await start_node(n)
        await asyncio.sleep(0.05)

    # Fail fast with a clear diagnostic if a node crashed immediately
    # (e.g. missing dependency, port already in use) instead of waiting
    # through the full discovery timeout and a cryptic connection error.
    await asyncio.sleep(3.0)
    dead = {n: p for n, p in processes.items() if p.returncode is not None}
    if dead:
        print("\n*** ERROR: the following node(s) exited immediately: ***", flush=True)
        for n in dead:
            logpath = os.path.join(BASE, f"run_{n}", "node_stdout.log")
            print(f"\n--- {n} exit code {processes[n].returncode} --- log: {logpath} ---", flush=True)
            try:
                with open(logpath, "r", errors="ignore") as f:
                    print(f.read()[-3000:], flush=True)
            except Exception as e:
                print(f"(could not read log: {e})", flush=True)
        print("\nFix the error above and re-run 'python harness.py'.", flush=True)
        sys.exit(1)

    watcher_task = asyncio.create_task(discovery_watcher())

    # wait for discovery to stabilize
    print("Waiting for peer discovery to stabilize...", flush=True)
    for _ in range(60):
        if all(n in discovery_done_time for n in NODES):
            break
        await asyncio.sleep(0.25)
    await asyncio.sleep(1.0)

    for n in NODES:
        if n in discovery_done_time:
            results["discovery"][n] = discovery_done_time[n] - proc_start_time[n]
        else:
            results["discovery"][n] = None
    print("Discovery times (s):", results["discovery"], flush=True)

    if any(v is None for v in results["discovery"].values()):
        print("\n*** WARNING: not all nodes discovered each other. ***", flush=True)
        print("If the logs below show 'Advertising Node' / 'Discovered Node'", flush=True)
        print("lines, discovery is working but just took longer than expected", flush=True)
        print("-- try again, it should register on the next print check.", flush=True)
        print("If the logs are still empty of those lines, it's more likely", flush=True)
        print("Windows Firewall silently blocking mDNS/UDP multicast: check", flush=True)
        print("Windows Defender Firewall -> Allow an app -> Python, and allow", flush=True)
        print("it on Private networks, then re-run.", flush=True)
        for n in NODES:
            logpath = os.path.join(BASE, f"run_{n}", "node_stdout.log")
            print(f"\n--- last lines of {n} log ({logpath}) ---", flush=True)
            try:
                with open(logpath, "r", errors="ignore") as f:
                    print(f.read()[-1500:], flush=True)
            except Exception as e:
                print(f"(could not read log: {e})", flush=True)

    # start websocket listener on D
    ws_task = asyncio.create_task(ws_listener_d())
    await asyncio.sleep(0.5)

    # Scenario I: all four nodes active
    await run_scenario("scenario_1_normal", ["A", "B", "C", "D"])

    # Scenario II: kill B
    print("Killing node B ...")
    await kill_node("B")
    await asyncio.sleep(1.0)
    await run_scenario("scenario_2_single_failure", ["A", "C", "D"])

    # Scenario III: kill C too
    print("Killing node C ...")
    await kill_node("C")
    await asyncio.sleep(1.0)
    await run_scenario("scenario_3_multi_failure", ["A", "D"])

    # cleanup
    try:
        ws_connection_holder["ws"] and await ws_connection_holder["ws"].close()
    except Exception:
        pass
    ws_task.cancel()
    for n in ["A", "D"]:
        await kill_node(n)

    watcher_task.cancel()
    for logf in log_file_handles.values():
        try:
            logf.close()
        except Exception:
            pass

    with open(f"{BASE}/results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    print("DONE", flush=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        import traceback
        traceback.print_exc()
        print("DONE_WITH_ERROR", flush=True)
