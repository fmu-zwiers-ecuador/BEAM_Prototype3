"""Shipping assets must resolve inside the Prototype3 checkout."""

from __future__ import annotations

import json
import os
from pathlib import Path
import runpy
from types import SimpleNamespace

from beamnode import paths


REPO = paths.REPO_ROOT
STORAGE = paths.PACKAGE_ROOT / "storage"
SUPERVISOR = paths.PACKAGE_ROOT / "supervisor"

MAPPED_FILES = [
    STORAGE / "shipping.py",
    STORAGE / "move_shipping_to_beamdrive.sh",
    SUPERVISOR / "retryqueue.py",
    SUPERVISOR / "ping_nodes_10min.py",
    SUPERVISOR / "retrylogic.sh",
    SUPERVISOR / "move_supervisor_data_to_beamdrive.sh",
    REPO / "config" / "node_states.json",
    REPO / "docs" / "shipping" / "README.md",
    REPO / "docs" / "shipping" / "node-shipping.md",
    REPO / "docs" / "shipping" / "bench-test.md",
    REPO / "docs" / "shipping" / "retry-queue.md",
]


def test_all_canonical_shipping_files_exist_once() -> None:
    missing = [path.relative_to(REPO).as_posix() for path in MAPPED_FILES if not path.is_file()]

    assert not missing
    assert not (SUPERVISOR / "data_collection").exists()
    assert not (SUPERVISOR / "node_states.json").exists()


def test_shipping_constants_use_shared_prototype3_paths() -> None:
    assert paths.NODE_STATES_JSON == REPO / "config" / "node_states.json"
    assert paths.MOVE_TO_BEAMDRIVE_SCRIPT == (
        SUPERVISOR / "move_supervisor_data_to_beamdrive.sh"
    )

    for root in (paths.PACKAGE_ROOT, REPO / "config", REPO / "deploy"):
        for path in root.rglob("*"):
            if path.is_file():
                text = path.read_text(encoding="utf-8", errors="ignore")
                assert "BEAMNode_Prototype2" not in text, path
                assert "supervisor/data_collection" not in text, path


def test_node_shipping_moves_fixture_into_timestamped_folder(tmp_path, monkeypatch) -> None:
    data_dir = tmp_path / "data"
    shipping_dir = tmp_path / "shipping"
    data_dir.mkdir()
    fixture = data_dir / "bench-fixture.txt"
    fixture.write_text("disposable bench data\n", encoding="utf-8")

    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "global": {
                    "base_dir": str(data_dir),
                    "ship_dir": str(shipping_dir),
                    "node_id": "fallback-node",
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(paths, "CONFIG_JSON", config_path)
    monkeypatch.setattr(paths, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        os,
        "uname",
        lambda: SimpleNamespace(nodename="bench-node"),
        raising=False,
    )

    runpy.run_path(str(STORAGE / "shipping.py"), run_name="shipping_test")

    destinations = list(shipping_dir.glob("data-bench-node-*/bench-fixture.txt"))
    assert len(destinations) == 1
    assert destinations[0].read_text(encoding="utf-8") == "disposable bench data\n"
    assert not fixture.exists()
