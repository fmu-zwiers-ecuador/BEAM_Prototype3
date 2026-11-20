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
    ],
)
def test_repository_paths_point_at_deploy_network(script: str) -> None:
    text = (NETWORK / script).read_text(encoding="utf-8")

    found = PI_PATH.findall(text)
    assert found, f"{script} should reference the Pi checkout"
    assert all(path.startswith("deploy/network") for path in found), found


def test_node_setup_does_not_install_itself_as_a_service() -> None:
    text = (NETWORK / "NodeInternet_Setup.sh").read_text(encoding="utf-8")

    exec_lines = re.findall(r"^ExecStart\w*=.*$", text, re.MULTILINE)
    assert "ExecStart=/usr/local/sbin/mesh-boot.sh" in exec_lines
    assert not [line for line in exec_lines if "NodeInternet_Setup.sh" in line]
    assert "User=pi" not in text


def test_batman_installer_uses_underscore_name() -> None:
    assert (NETWORK / "batman" / "install_batman.sh").is_file()
    assert not (NETWORK / "batman" / "install-batman.sh").exists()


def test_duplicate_mesh_setup_is_not_ported() -> None:
    assert not list(paths.REPO_ROOT.joinpath("deploy").rglob("mesh_setup"))


def test_node_setup_retires_legacy_nodeinternet_unit() -> None:
    text = (NETWORK / "NodeInternet_Setup.sh").read_text(encoding="utf-8")

    assert "LEGACY_UNIT=/etc/systemd/system/nodeinternet.service" in text
    # Only retire the unit if it launches the old installer, never an unrelated one.
    assert re.search(r"grep -Eq '\^ExecStart\.\*NodeInternet_Setup", text)
    assert "systemctl disable --now nodeinternet.service" in text
    assert 'rm -f "$LEGACY_UNIT"' in text
    # Retirement must happen before the first daemon-reload and before either
    # replacement unit is enabled.
    retire = text.index("systemctl disable --now nodeinternet.service")
    assert retire < text.index("systemctl daemon-reload")
    assert retire < text.index("systemctl enable mesh-boot.service")
    assert retire < text.index("systemctl enable mesh-timesync.service")
    # A failed disable must stop the installer, not be ignored.
    assert "systemctl disable --now nodeinternet.service || true" not in text
