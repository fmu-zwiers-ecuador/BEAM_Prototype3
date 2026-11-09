"""The commands in water-quality.md must work on a fresh Pi checkout.

A bench Pi runs these scripts with ``sudo`` from a plain checkout, with no
``pip install`` of this project. These tests check what can be checked without
hardware: every documented command makes ``beamnode`` importable, and every
library the Atlas scripts import is declared and has documented install steps.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from beamnode import paths

DOC = paths.REPO_ROOT / "docs" / "sensors" / "water-quality.md"
ATLAS_DIRS = [
    paths.PACKAGE_ROOT / "cli" / "atlas",
    paths.SENSORS_DIR / paths.ATLAS_FOLDER,
]

#: Import name -> (name in the ``node`` extra, Raspberry Pi OS package).
LIBRARIES = {
    "serial": ("pyserial", "python3-serial"),
    "smbus2": ("smbus2", "python3-smbus2"),
}

COMMAND = re.compile(r"^.*\bpython3? .*\.py\b.*$", re.MULTILINE)
DOCUMENTED = re.compile(
    rf"^sudo env PYTHONPATH=(?P<pythonpath>{paths.PI_CHECKOUT}/[\w./-]+) "
    rf"python3 {paths.PI_CHECKOUT}/(?P<script>[\w./-]+\.py)$"
)


def _commands() -> list[str]:
    return [line.strip() for line in COMMAND.findall(DOC.read_text(encoding="utf-8"))]


def _atlas_scripts() -> list[Path]:
    return sorted(path for folder in ATLAS_DIRS for path in folder.glob("*.py"))


def _third_party_imports(path: Path) -> set[str]:
    """Top-level modules a script imports that are neither stdlib nor beamnode."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
        elif (
            isinstance(node, ast.Call)
            and ast.unparse(node.func) == "importlib.import_module"
            and node.args
            and isinstance(node.args[0], ast.Constant)
        ):
            names.add(str(node.args[0].value))
    top_level = {name.split(".")[0] for name in names}
    return top_level - set(sys.stdlib_module_names) - {"beamnode"}


def _node_extra() -> set[str]:
    pyproject = tomllib.loads(
        (paths.REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )
    requirements = pyproject["project"]["optional-dependencies"]["node"]
    return {re.split(r"[<>=!~ \[;]", requirement)[0].lower() for requirement in requirements}


def test_doc_has_commands() -> None:
    assert len(_commands()) >= 5


@pytest.mark.parametrize("command", _commands())
def test_documented_command_can_import_beamnode(command: str) -> None:
    match = DOCUMENTED.match(command)
    assert match, (
        "run Atlas scripts as 'sudo env PYTHONPATH=<checkout>/src python3 "
        f"<checkout>/<script>': {command}"
    )
    assert (paths.REPO_ROOT / match["script"]).is_file()

    # Map the Pi checkout onto this checkout, then import the way root would:
    # -S ignores site-packages, so only PYTHONPATH can supply beamnode.
    pythonpath = paths.REPO_ROOT / Path(match["pythonpath"]).relative_to(paths.PI_CHECKOUT)
    result = subprocess.run(
        [sys.executable, "-S", "-c", "import beamnode.paths"],
        env={**os.environ, "PYTHONPATH": str(pythonpath)},
        cwd=paths.REPO_ROOT.anchor,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_beamnode_is_not_importable_without_pythonpath() -> None:
    """Guards the test above: -S alone must not find beamnode."""
    env = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
    result = subprocess.run(
        [sys.executable, "-S", "-c", "import beamnode.paths"],
        env=env,
        cwd=paths.REPO_ROOT.anchor,
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0
    assert "ModuleNotFoundError" in result.stderr


@pytest.mark.parametrize("script", _atlas_scripts(), ids=lambda path: path.name)
def test_atlas_script_libraries_are_declared_and_documented(script: Path) -> None:
    doc = DOC.read_text(encoding="utf-8")
    declared = _node_extra()
    for module in sorted(_third_party_imports(script)):
        assert module in LIBRARIES, f"{script.name} imports unknown library {module}"
        requirement, apt_package = LIBRARIES[module]
        assert requirement in declared, f"{requirement} is missing from the node extra"
        assert apt_package in doc, f"{DOC.name} does not install {apt_package}"
