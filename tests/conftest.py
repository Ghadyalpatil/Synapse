"""
SYNAPSE shared pytest fixtures for offline unit and integration tests.
All tests run completely in-process with no network, no NTP, no cloud.
"""

import asyncio
import os
import pytest
from pathlib import Path

# Ensure the offline clock anchor code does not fail in CI or test
# environments (no var/ dir may exist). Patch VAR_DIR to tmp_path.
os.environ.setdefault("SYNAPSE_DATA_DIR", str(Path(__file__).parent / "tmp_data"))
os.environ.setdefault("SYNAPSE_KEYS_DIR", str(Path(__file__).parent / "tmp_keys"))


@pytest.fixture(scope="session", autouse=True)
def patch_offline_clock(tmp_path_factory):
    """
    Applies the clock anchor correction once per test session using a temp dir.
    Ensures all timestamp comparisons use the corrected offline clock.
    """
    from synapse import clock
    run_dir = tmp_path_factory.mktemp("run")
    clock.apply_anchor_correction(run_dir)
    yield


@pytest.fixture
def tmp_db(tmp_path):
    """Provides an ephemeral in-process SQLite database for tests."""
    from synapse.storage.database import Database
    return Database(tmp_path / "test_node.db")
