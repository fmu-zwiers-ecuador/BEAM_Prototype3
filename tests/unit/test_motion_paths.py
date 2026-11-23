"""Reviewer-owned path checks for the motion port in issue #8."""

from __future__ import annotations

import os
from pathlib import Path

from beamnode import paths


REPO = paths.REPO_ROOT
MOTION = REPO / "src/beamnode/motion"
SYSTEMD = REPO / "deploy/systemd"
DOC = REPO / "docs/motion/motion-capture-system.md"


def test_motion_modules_use_shared_config_path() -> None:
    for name in (
        "beam_motion_trigger.py",
        "camera_motion_capture.py",
        "audiomoth_motion_record.py",
    ):
        text = (MOTION / name).read_text(encoding="utf-8")
        assert "from beamnode.paths import CONFIG_JSON" in text
        assert "CONFIG_PATH" in text and "CONFIG_JSON" in text
        assert "scripts/node/config.json" not in text


def test_runtime_paths_do_not_discard_repository_root() -> None:
    offenders: list[str] = []
    for path in MOTION.glob("*.py"):
        if 'Path(REPO_ROOT, "/' in path.read_text(encoding="utf-8"):
            offenders.append(path.name)
    assert not offenders, f"absolute child paths discard REPO_ROOT in: {offenders}"


def test_motion_runtime_paths_are_consistent() -> None:
    trigger = (MOTION / "beam_motion_trigger.py").read_text(encoding="utf-8")
    worker = (MOTION / "motion_merge_worker.py").read_text(encoding="utf-8")
    service = (SYSTEMD / "beam-motion-merge.service").read_text(encoding="utf-8")

    assert 'DEFAULT_DATA_DIR = Path("/home/pi/data")' in trigger
    assert 'LUX_LOG_PATH = DEFAULT_DATA_DIR / "tsl2591/lux_data.json"' in trigger
    assert 'VIDEO_PROCESSING_LOG_PATH = LOGS_DIR / "motion_video_processing.log"' in trigger
    assert 'DEFAULT_QUEUE_DIR = Path("/home/pi/data/motion_events")' in worker
    assert 'VIDEO_PROCESSING_LOG_PATH = LOGS_DIR / "motion_video_processing.log"' in worker
    assert "--queue-dir /home/pi/data/motion_events" in service


def test_repository_logs_use_shared_log_directory() -> None:
    text = (MOTION / "motion_logging.py").read_text(encoding="utf-8")
    assert "from beamnode.paths import LOGS_DIR" in text
    assert 'LOG_PATH = LOGS_DIR / "motion.log"' in text
    assert "BEAMNode_Prototype" not in text


def test_merge_service_uses_prototype3_checkout() -> None:
    text = (SYSTEMD / "beam-motion-merge.service").read_text(encoding="utf-8")
    expected = str(paths.PI_CHECKOUT / "src/beamnode/motion")
    assert f"WorkingDirectory={expected}" in text
    assert f"ExecStart=/usr/bin/python3 {expected}/motion_merge_worker.py" in text
    assert "BEAMNode_Prototype" not in text


def test_installer_scripts_are_executable() -> None:
    scripts = (
        SYSTEMD / "install_motion_merge_service.sh",
        SYSTEMD / "disable_standalone_motion_services.sh",
    )
    assert all(os.access(path, os.X_OK) for path in scripts)


def test_documentation_uses_prototype3_paths() -> None:
    text = DOC.read_text(encoding="utf-8")
    assert "scripts/node/config.json" not in text
    assert "config/config.json" in text
    assert "BEAMNode_Prototype" not in text
    assert str(paths.PI_CHECKOUT / "deploy/systemd") in text
