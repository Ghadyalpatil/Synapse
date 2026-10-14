# Benchmark Kit — Quantitative Results for the Mesh Messaging Paper

> **Update:** if you hit `ConnectionRefusedError` / `Discovery times: {all None}`
> on your first run, that was a bug in `harness.py` (it launched nodes with
> the literal command `python3`, which on Windows is often just an inert
> Microsoft Store stub rather than a real interpreter — so none of the four
> node processes ever actually started). Fixed: it now launches nodes using
> `sys.executable`, i.e. the exact same interpreter you're running the
> harness with. Re-download/replace `harness.py` and try again. It will
> also now fail fast with a readable error (instead of a deep traceback) if
> a node process dies immediately, and will print each node's log if peer
> discovery doesn't complete.

This folder contains a benchmark harness that runs your **actual, unmodified**
`mesh-networkTEST3/backend` code across the three scenarios described in the
paper (normal operation, single-node failure, multiple-node failure) and
measures real numbers for:

- Peer discovery time (via Zeroconf/mDNS, as it actually happens)
- Encrypted, end-to-end packet delivery latency (A → D), per scenario
- Packet delivery success rate, per scenario
- CPU and memory usage of each node process, per scenario
- Curve25519 encryption/decryption timing (isolated microbenchmark)

Nothing in your `backend/` folder is modified. The harness makes 4 temporary
copies of it (`benchkit/_run/run_A` … `run_D`) so each simulated node gets
its own SQLite database file instead of contending for one shared file.

## Why you're running this instead of me

I ran this in my own sandboxed execution environment first, and confirmed
the code itself works correctly (Zeroconf discovery, encryption, and the
full send → relay → decrypt → deliver pipeline all function as described).
However, that sandbox only has a single CPU core, and reliably running 3–4
concurrent node processes (each spinning up asyncio + FastAPI/uvicorn +
Zeroconf) needs more than one core — attempts either hung or produced
timings so distorted by CPU starvation that they would not have honestly
reflected real performance. Your paper's own hardware table (Table III)
already describes an Intel i5/i7 with 16 GB RAM — exactly the kind of
multi-core machine this needs, and very likely the same machine you already
used to build and demo the prototype.

## 1. Setup

Place this `benchkit` folder as a **sibling** of your `backend` folder:

```
mesh-networkTEST3/
├── backend/
├── frontend/
└── benchkit/
    ├── harness.py
    ├── bench_encrypt.py
    ├── bench_decrypt.py
    └── README.md   (this file)
```

Install dependencies (same ones your project already needs, plus a couple
used only by the benchmark):

```bash
pip install fastapi uvicorn websockets zeroconf pynacl requests psutil
```

## 2. Run the network-level benchmark (discovery, latency, success rate, resource usage)

From inside `benchkit/`:

```bash
python3 harness.py
```

This takes roughly 60–90 seconds. It will:
1. Start nodes A, B, C, D and wait for them to discover each other.
2. Send 30 messages A → D with all four nodes up (Scenario I).
3. Kill node B, send 30 more messages A → D (Scenario II).
4. Kill node C, send 30 more messages A → D (Scenario III).
5. Write everything to `benchkit/_run/results.json` and print a summary.

If a firewall prompt appears (macOS/Windows) asking whether Python can
accept incoming network connections, allow it — the socket server and
Zeroconf discovery need it.

## 3. Run the encryption/decryption microbenchmark

From inside `benchkit/` (after step 2 has run at least once, so that
`_run/run_A` and `_run/run_D` exist with generated keys):

```bash
python3 bench_encrypt.py
python3 bench_decrypt.py
```

This writes `benchkit/enc_times.json` and `benchkit/dec_times.json`,
overwriting the placeholder copies included in this kit (which came from
*my* sandboxed run of your code, included here just so you can see the
expected format).

## 4. Send the results back

Please send back these three files:
- `_run/results.json`
- `enc_times.json`
- `dec_times.json`

I'll turn them directly into the quantitative results table, the five
performance charts, and the accompanying methodology text in the paper —
using your real measured numbers, not placeholders.

## Notes on what the numbers will (and won't) show

Because Zeroconf/mDNS on a single LAN segment causes every node to
directly discover every other node, node A and node D remain directly
connected in every scenario in this test (matching the topology in Fig. 2
of the paper, where the A–D edge is never removed). This means killing B
and/or C will most likely **not** change A→D latency much — the resilience
story here is "the framework keeps working when nodes disappear," not
"traffic reroutes through a different node," because in this deployment
A and D never depended on a specific intermediate hop in the first place.
That's a genuine and worth-reporting finding, not a flaw in the test.

Separately, while reading through the code to build this harness, I noticed
`heartbeat_loop()` currently emits a periodic heartbeat event but does not
call `peer_registry.mark_offline()` on timeout — so the "automatic offline
detection" behavior described in the paper (Sections III.D, V.D.3, VI) isn't
actually implemented yet in this codebase. Worth deciding whether to (a)
soften that language to describe heartbeat as connectivity *monitoring*
rather than automatic *removal*, or (b) add the timeout-triggered
`mark_offline()` call so the claim is accurate — happy to help with either.
