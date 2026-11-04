"""Guardrails that keep parallel porting work consistent.

Checks skip while the area they cover has not been ported yet, so they stay
green on the bare scaffold and start enforcing as code lands.
"""

from __future__ import annotations

import json
import py_compile
import re
from pathlib import Path

import pytest

from beamnode import paths

REPO = paths.REPO_ROOT
SKIP_DIRS = {".git", "legacy", "__pycache__", ".pytest_cache", "node_modules"}
TEXT_SUFFIXES = {".py", ".sh", ".service", ".timer", ".toml", ".json", ".md", ".yml", ".yaml"}
PI_PATH = re.compile(r"/home/pi/BEAM_Prototype3/([\w./-]+)")
RUNTIME_DIRS = {"data", "logs", "shipping"}


def _files(*roots: str, suffixes: set[str] | None = None) -> list[Path]:
    found: list[Path] = []
    for root in roots:
        base = REPO / root
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or SKIP_DIRS & set(path.relative_to(REPO).parts):
                continue
            if suffixes is None or path.suffix in suffixes:
                found.append(path)
    return found


def _rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def test_python_files_compile(tmp_path: Path) -> None:
    files = _files("src", "deploy", "tests/hardware", suffixes={".py"})
    assert files, "scaffold should contain at least one Python file"
    for index, path in enumerate(files):
        try:
            py_compile.compile(str(path), cfile=str(tmp_path / f"{index}.pyc"), doraise=True)
        except py_compile.PyCompileError as exc:
            pytest.fail(f"{_rel(path)} does not compile: {exc.msg}")


def test_production_code_does_not_mention_prototype2() -> None:
    offenders = [
        _rel(p)
        for p in _files("src", "deploy", suffixes=TEXT_SUFFIXES)
        if "BEAMNode_Prototype2" in p.read_text(encoding="utf-8", errors="ignore")
    ]
    assert not offenders, f"Prototype2 referenced in: {offenders}"


def test_hardcoded_pi_paths_exist_in_repo() -> None:
    checked = 0
    missing: list[str] = []
    for path in _files("src", "deploy", "tests/hardware", suffixes=TEXT_SUFFIXES):
        text = path.read_text(encoding="utf-8", errors="ignore")
        for match in PI_PATH.finditer(text):
            relative = match.group(1).rstrip(".,:;)")
            if relative.split("/")[0] in RUNTIME_DIRS or "*" in relative:
                continue
            checked += 1
            if not (REPO / relative).exists():
                missing.append(f"{_rel(path)}: /home/pi/BEAM_Prototype3/{relative}")
    if not checked:
        pytest.skip("no hard-coded /home/pi/BEAM_Prototype3 paths yet")
    assert not missing, f"paths that do not exist in the repository: {missing}"


def test_sensors_with_frequency_resolve_to_scripts() -> None:
    if not paths.CONFIG_JSON.is_file():
        pytest.skip("config/config.json has not been ported yet")
    config = json.loads(paths.CONFIG_JSON.read_text(encoding="utf-8"))
    sensors = {
        name: section
        for name, section in config.items()
        if isinstance(section, dict) and "frequency" in section
    }
    if not sensors:
        pytest.skip("config.json defines no sensors with a frequency")
    unresolved = [
        name
        for name, section in sensors.items()
        if not paths.sensor_script(name, str(section.get("script_name", ""))).is_file()
    ]
    assert not unresolved, f"sensors with no script under src/beamnode/sensors/: {unresolved}"


def test_atlas_sections_share_one_folder() -> None:
    assert paths.sensor_folder("atlas_ph") == "atlas_sci"
    assert paths.sensor_folder("atlas_ec") == "atlas_sci"
    assert paths.sensor_folder("bme280") == "bme280"
    assert paths.sensor_script("atlas_ph", "log_ph.py") == (
        paths.SENSORS_DIR / "atlas_sci" / "log_ph.py"
    )


def test_shell_scripts_use_lf_endings() -> None:
    scripts = _files("src", "deploy", "tests", suffixes={".sh"})
    if not scripts:
        pytest.skip("no shell scripts have been ported yet")
    crlf = [_rel(p) for p in scripts if b"\r\n" in p.read_bytes()]
    assert not crlf, f"CRLF line endings in: {crlf}"
