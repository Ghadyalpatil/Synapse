"""
SYNAPSE — Offline Hardware Clock & Monotonic Timekeeping
Provides resilient timestamp generation for fully air-gapped Raspberry Pi nodes
that have no NTP server access and may start with an incorrect system clock.

Strategy:
  1. Use time.monotonic() for all internal interval/delta calculations.
  2. Use a local epoch anchor file (var/run/epoch_anchor.json) to persist
     the last known good epoch offset across reboots.
  3. If system clock appears far behind a hardware RTC reading or persisted
     anchor, apply a correction to keep inter-node timestamps consistent.
  4. Never contact any external server.
"""

import json
import logging
import time
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger("synapse.clock")

_ANCHOR_FILENAME = "epoch_anchor.json"
_BOOT_MONO = time.monotonic()          # Monotonic reference at import time
_BOOT_WALL = time.time()               # Wall clock at import time
_OFFSET_CORRECTION: float = 0.0       # Applied after anchor load


def load_epoch_anchor(run_dir: Path) -> Tuple[float, float]:
    """
    Loads persisted anchor (wall_time, mono_reference) from disk.
    Returns (saved_wall_time, saved_mono) or (0.0, 0.0) if not found.
    """
    anchor_path = run_dir / _ANCHOR_FILENAME
    if anchor_path.exists():
        try:
            data = json.loads(anchor_path.read_text())
            return float(data["wall_time"]), float(data["mono_ref"])
        except Exception as e:
            logger.debug(f"[Clock] Anchor load failed: {e}")
    return 0.0, 0.0


def save_epoch_anchor(run_dir: Path):
    """Persists the current wall-clock epoch to disk for next-boot continuity."""
    run_dir.mkdir(parents=True, exist_ok=True)
    anchor_path = run_dir / _ANCHOR_FILENAME
    try:
        anchor_path.write_text(json.dumps({
            "wall_time": time.time(),
            "mono_ref": time.monotonic(),
            "node_boot_wall": _BOOT_WALL
        }, indent=2))
    except Exception as e:
        logger.warning(f"[Clock] Could not persist epoch anchor: {e}")


def apply_anchor_correction(run_dir: Path):
    """
    Compares persisted anchor against current wall clock.
    If the current clock is suspiciously far behind the anchor (e.g. after
    a reboot without RTC battery), applies a correction offset so that
    event timestamps remain monotonically increasing across reboots.
    """
    global _OFFSET_CORRECTION
    saved_wall, saved_mono = load_epoch_anchor(run_dir)
    if saved_wall <= 0:
        # No anchor yet — persist and return
        save_epoch_anchor(run_dir)
        return

    now_wall = time.time()
    # If current clock is more than 60s behind the last saved wall time,
    # the system clock is wrong (no RTC or no NTP). Apply a forward offset.
    if saved_wall > now_wall + 60:
        _OFFSET_CORRECTION = saved_wall - now_wall + 1.0  # +1 second forward margin
        logger.warning(
            f"[Clock] System clock appears stale. "
            f"Saved anchor: {saved_wall:.0f}, current: {now_wall:.0f}. "
            f"Applying correction offset: +{_OFFSET_CORRECTION:.1f}s"
        )
    else:
        _OFFSET_CORRECTION = 0.0

    save_epoch_anchor(run_dir)


def now() -> float:
    """
    Returns a corrected epoch timestamp safe for air-gapped operation.
    Uses wall clock + any applied offset correction from persisted anchor.
    """
    return time.time() + _OFFSET_CORRECTION


def monotonic_elapsed(reference_mono: float) -> float:
    """Returns elapsed seconds since a monotonic reference — never affected by clock changes."""
    return time.monotonic() - reference_mono


def format_iso(ts: Optional[float] = None) -> str:
    """Returns a local ISO-8601 string for a timestamp (no UTC assumption)."""
    import datetime
    t = ts if ts is not None else now()
    return datetime.datetime.fromtimestamp(t).strftime("%Y-%m-%dT%H:%M:%S")
