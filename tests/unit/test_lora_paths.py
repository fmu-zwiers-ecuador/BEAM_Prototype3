"""LoRa deployment assets must resolve inside the Prototype3 checkout."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from beamnode import paths

REPO = paths.REPO_ROOT
LORA = paths.PACKAGE_ROOT / "transport" / "lora"
SYSTEMD = REPO / "deploy" / "systemd"
SETUP = REPO / "deploy" / "setup"

MAPPED_FILES = [
    LORA / "node_send.py",
    LORA / "node_time_request.py",
    LORA / "supervisor_receive.py",
    SYSTEMD / "lora-node-send.service",
    SYSTEMD / "lora-node-send.timer",
    SYSTEMD / "lora-supervisor-receive.service",
    SETUP / "install_lora_automation.sh",
    SETUP / "lora_packages.txt",
    REPO / "docs" / "lora" / "sending-protocol.md",
]


def test_all_mapped_lora_files_exist() -> None:
    missing = [path.relative_to(REPO).as_posix() for path in MAPPED_FILES if not path.is_file()]
    assert not missing


def test_time_request_uses_shared_config_path() -> None:
    source = (LORA / "node_time_request.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    imports = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "beamnode.paths"
        for alias in node.names
    }
    assert "CONFIG_JSON" in imports
    assert "BEAMNode_Prototype2" not in source
    assert "scripts/node/config.json" not in source


@pytest.mark.parametrize(
    ("unit_name", "script_name"),
    [
        ("lora-node-send.service", "node_send.py"),
        ("lora-supervisor-receive.service", "supervisor_receive.py"),
    ],
)
def test_lora_services_use_prototype3_paths(unit_name: str, script_name: str) -> None:
    text = (SYSTEMD / unit_name).read_text(encoding="utf-8")

    assert "WorkingDirectory=/home/pi/BEAM_Prototype3" in text
    assert "Environment=PYTHONPATH=/home/pi/BEAM_Prototype3/src" in text
    assert (
        "ExecStart=/usr/bin/python3 "
        f"/home/pi/BEAM_Prototype3/src/beamnode/transport/lora/{script_name}"
    ) in text
    assert "BEAMNode_Prototype2" not in text


def test_lora_timer_targets_sender_service() -> None:
    text = (SYSTEMD / "lora-node-send.timer").read_text(encoding="utf-8")

    assert "OnCalendar=*-*-* 14:00:00" in text
    assert "Persistent=true" in text
    assert "Unit=lora-node-send.service" in text


def test_lora_installer_uses_split_prototype3_directories() -> None:
    text = (SETUP / "install_lora_automation.sh").read_text(encoding="utf-8")

    assert 'PROJECT_ROOT="/home/pi/BEAM_Prototype3"' in text
    assert 'LORA_DIR="$PROJECT_ROOT/src/beamnode/transport/lora"' in text
    assert 'UNIT_DIR="$PROJECT_ROOT/deploy/systemd"' in text
    assert 'CONFIG_PATH="$PROJECT_ROOT/config/config.json"' in text
    assert 'cp "$UNIT_DIR/lora-node-send.service" "$SYSTEMD_DIR/"' in text
    assert 'cp "$UNIT_DIR/lora-supervisor-receive.service" "$SYSTEMD_DIR/"' in text
    assert (
        "/usr/bin/python3 "
        "/home/pi/BEAM_Prototype3/src/beamnode/transport/lora/node_time_request.py"
    ) in text
    assert "BEAMNode_Prototype2" not in text


def test_lora_package_list_covers_hardware_imports() -> None:
    packages = {
        line.strip()
        for line in (SETUP / "lora_packages.txt").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }

    assert packages == {
        "adafruit-blinka",
        "adafruit-circuitpython-rfm9x",
        "spidev",
        "RPi.GPIO",
    }
