"""Atlas loggers and tools must sit where the scheduler and operators expect them.

Also guards the pH calibration wizard against regressing to the
dissolved-oxygen wizard it was originally copied from.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from beamnode import paths

ATLAS = paths.SENSORS_DIR / paths.ATLAS_FOLDER
CLI_ATLAS = paths.PACKAGE_ROOT / "cli" / "atlas"
CALIBRATE_PH = CLI_ATLAS / "calibrate_ph.py"

#: The ``atlas_*`` sections and ``script_name`` values from Prototype2's config.json.
ATLAS_SECTIONS = {
    "atlas_do": "log_atlas_do.py",
    "atlas_ec": "log_atlas_ec.py",
    "atlas_orp": "log_atlas_orp.py",
    "atlas_ph": "log_atlas_ph.py",
    "atlas_rtd": "log_atlas_rtd.py",
}

CLI_TOOLS = [
    "calibrate_do.py",
    "calibrate_ec.py",
    "calibrate_orp.py",
    "calibrate_ph.py",
    "check_ec_cal.py",
    "fix_ec_address.py",
    "switch_do_to_i2c.py",
    "switch_ec_to_i2c.py",
    "switch_orp_to_i2c.py",
    "switch_ph_to_i2c.py",
    "switch_rtd_to_i2c.py",
]

PH_CALIBRATION_COMMANDS = {"Cal,mid,7.00", "Cal,low,4.00", "Cal,high,10.00", "Cal,?"}
#: Commands the dissolved-oxygen wizard sends that a pH circuit must never receive.
DO_CALIBRATION_COMMANDS = {"Cal", "Cal,0", "Cal,clear"}
#: An EZO calibration command: ``Cal`` alone or ``Cal,<args>`` with no spaces.
EZO_CAL_COMMAND = re.compile(r"Cal(,[^\s]*)?")


def string_constants(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str)
    }


@pytest.mark.parametrize(("section", "script_name"), sorted(ATLAS_SECTIONS.items()))
def test_atlas_section_resolves_to_shared_logger(section: str, script_name: str) -> None:
    script = paths.sensor_script(section, script_name)

    assert script == ATLAS / script_name
    assert script.is_file()


def test_atlas_folder_has_only_the_five_loggers() -> None:
    loggers = {path.name for path in ATLAS.glob("log_*.py")}

    assert loggers == set(ATLAS_SECTIONS.values())


@pytest.mark.parametrize("tool", CLI_TOOLS)
def test_atlas_cli_tool_exists(tool: str) -> None:
    assert (CLI_ATLAS / tool).is_file()


def test_water_quality_docs_exist() -> None:
    assert (paths.REPO_ROOT / "docs" / "sensors" / "water-quality.md").is_file()


def test_ph_tool_targets_ph_section_and_address() -> None:
    constants = string_constants(CALIBRATE_PH)

    assert "atlas_ph" in constants
    assert "0x63" in constants
    assert "atlas_do" not in constants
    assert "0x61" not in constants


def test_ph_tool_sends_only_ph_calibration_commands() -> None:
    calibration_commands = {
        value
        for value in string_constants(CALIBRATE_PH)
        if EZO_CAL_COMMAND.fullmatch(value)
    }

    assert calibration_commands == PH_CALIBRATION_COMMANDS
    assert not calibration_commands & DO_CALIBRATION_COMMANDS


def test_ph_tool_does_not_describe_dissolved_oxygen() -> None:
    source = CALIBRATE_PH.read_text(encoding="utf-8").lower()

    assert "dissolved oxygen" not in source
