"""Ported detection and sensor scripts must get config.json from beamnode.paths."""

from __future__ import annotations

import ast

import pytest

from beamnode import paths

SCRIPTS = [
    "cli/detect.py",
    "sensors/ahtx0/log_ahtx0_paramdata.py",
    "sensors/bme280/log_env_data.py",
    "sensors/bme680/log_env680_data.py",
    "sensors/tsl2591/log_lux_data.py",
    "sensors/ultrasonic/log_ultrasonic.py",
]


@pytest.mark.parametrize("script", SCRIPTS)
def test_script_uses_shared_config_path(script: str) -> None:
    tree = ast.parse((paths.PACKAGE_ROOT / script).read_text(encoding="utf-8"))

    imported = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "beamnode.paths"
        for alias in node.names
    }
    assert "CONFIG_JSON" in imported

    built_paths = [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and (node.value == "config.json" or node.value.endswith("/config.json"))
    ]
    assert not built_paths, f"{script} builds its own config path: {built_paths}"
