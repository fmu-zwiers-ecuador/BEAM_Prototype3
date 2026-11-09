"""Ported network scripts must deploy from main and live under deploy/network."""

from __future__ import annotations

import re

import pytest

from beamnode import paths

NETWORK = paths.REPO_ROOT / "deploy" / "network"
PI_PATH = re.compile(r"/home/pi/BEAM_Prototype3/([\w./-]+)")


def test_repull_clones_main_explicitly() -> None:
    script = (NETWORK / "repull.sh").read_text(encoding="utf-8")

    assert re.search(r"git clone\s+(--branch|-b)\s+main\s+\S+/BEAM_Prototype3\.git", script)


@pytest.mark.parametrize(
    "script",
    [
        "monitor_internet.sh",
        "restart_internet.sh",
        "set_internetservice.sh",
        "NodeInternet_Setup.sh",
    ],
)
def test_repository_paths_point_at_deploy_network(script: str) -> None:
    text = (NETWORK / script).read_text(encoding="utf-8")

    found = PI_PATH.findall(text)
    assert found, f"{script} should reference the Pi checkout"
    assert all(path.startswith("deploy/network") for path in found), found


def test_batman_installer_uses_underscore_name() -> None:
    assert (NETWORK / "batman" / "install_batman.sh").is_file()
    assert not (NETWORK / "batman" / "install-batman.sh").exists()


def test_duplicate_mesh_setup_is_not_ported() -> None:
    assert not list(paths.REPO_ROOT.joinpath("deploy").rglob("mesh_setup"))
