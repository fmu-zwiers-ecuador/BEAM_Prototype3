"""Shared repository path constants.

Every script that needs a file in this repository imports its location from
here instead of building its own path. During Sprint 1 settings live in
``config/config.json``; a later milestone moves them to ``/etc/beamnode/`` and
replaces these constants with a ``RuntimePaths`` object.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

#: Where the repository is checked out on a Raspberry Pi. Deployed systems pin
#: this checkout to ``main``.
PI_CHECKOUT = PurePosixPath("/home/pi/BEAM_Prototype3")

#: Repository root, derived from this file (``src/beamnode/paths.py``).
REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGE_ROOT = Path(__file__).resolve().parent

CONFIG_DIR = REPO_ROOT / "config"
CONFIG_JSON = CONFIG_DIR / "config.json"
LOGS_DIR = REPO_ROOT / "logs"
SENSORS_DIR = PACKAGE_ROOT / "sensors"

#: Config sections with this prefix share one script folder.
ATLAS_PREFIX = "atlas_"
ATLAS_FOLDER = "atlas_sci"


def sensor_folder(section: str) -> str:
    """Return the folder name under ``sensors/`` for a config section."""
    return ATLAS_FOLDER if section.startswith(ATLAS_PREFIX) else section


def sensor_script(section: str, script_name: str) -> Path:
    """Return the path the scheduler runs for ``section`` and ``script_name``."""
    return SENSORS_DIR / sensor_folder(section) / script_name
