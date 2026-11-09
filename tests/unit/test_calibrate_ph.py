"""The pH wizard must only calibrate a pH circuit, using the pH buffer points."""

from __future__ import annotations

import builtins
import importlib.util
import json
import sys
import types
from pathlib import Path
from typing import Any

import pytest

from beamnode import paths


class FakeCircuit:
    """Answers the EZO commands the wizard sends and records them."""

    def __init__(
        self,
        identity: str = "?I,pH,2.16",
        rejected: tuple[str, ...] = (),
        reported_points: int | None = None,
    ) -> None:
        self.identity = identity
        self.rejected = rejected
        self.reported_points = reported_points
        self.points = 0
        self.sent: list[str] = []

    def __enter__(self) -> "FakeCircuit":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def query(self, command: str, timeout: float = 0, num_bytes: int = 31):
        self.sent.append(command)
        if command in self.rejected:
            return 2, "", [2]
        if command == "I":
            return 1, self.identity, [1]
        if command == "Cal,?":
            points = self.points
            if self.reported_points is not None:
                points = self.reported_points
            return 1, f"?Cal,{points}", [1]
        if command == "Cal,mid,7.00":
            self.points = 1
        elif command.startswith("Cal,"):
            self.points += 1
        elif command == "R":
            return 1, "7.012", [1]
        return 1, "", [1]

    @property
    def calibrations(self) -> list[str]:
        return [c for c in self.sent if c.startswith("Cal,") and c != "Cal,?"]


@pytest.fixture
def wizard(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Any:
    monkeypatch.setitem(
        sys.modules, "fcntl", types.SimpleNamespace(ioctl=lambda *args: None)
    )
    spec = importlib.util.spec_from_file_location(
        "calibrate_ph", paths.PACKAGE_ROOT / "cli" / "atlas" / "calibrate_ph.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    config = tmp_path / "config.json"
    config.write_text(
        json.dumps(
            {
                "atlas_ph": {"enabled": False, "i2c_bus": 1, "address_hex": "0x63"},
                "atlas_do": {"enabled": False, "address_hex": "0x61"},
            }
        )
    )
    monkeypatch.setattr(module, "CONFIG_PATH", str(config))
    monkeypatch.setattr(module, "countdown", lambda seconds: None)
    return module


def run(
    wizard: Any,
    monkeypatch: pytest.MonkeyPatch,
    circuit: FakeCircuit,
    answers: list[str],
) -> dict[str, Any]:
    opened: list[tuple[int, int]] = []

    def open_circuit(address: int, bus: int = 1) -> FakeCircuit:
        opened.append((address, bus))
        return circuit

    replies = iter(answers)
    monkeypatch.setattr(wizard, "AtlasI2CDevice", open_circuit)
    monkeypatch.setattr(builtins, "input", lambda *args: next(replies))
    wizard.main()
    assert opened in ([], [(0x63, 1)])
    return json.loads(Path(wizard.CONFIG_PATH).read_text())


def test_three_point_calibration(wizard, monkeypatch) -> None:
    circuit = FakeCircuit()
    config = run(wizard, monkeypatch, circuit, ["", "", "", ""])

    assert circuit.calibrations == ["Cal,mid,7.00", "Cal,low,4.00", "Cal,high,10.00"]
    assert config["atlas_ph"]["enabled"] is True
    assert config["atlas_do"] == {"enabled": False, "address_hex": "0x61"}


def test_low_and_high_points_are_optional(wizard, monkeypatch) -> None:
    circuit = FakeCircuit()
    config = run(wizard, monkeypatch, circuit, ["", "", "skip", "skip"])

    assert circuit.calibrations == ["Cal,mid,7.00"]
    assert config["atlas_ph"]["enabled"] is True


@pytest.mark.parametrize("identity", ["?I,DO,2.16", "?I,ORP,2.0", "?I,EC,2.1"])
def test_other_circuits_are_refused(wizard, monkeypatch, identity: str) -> None:
    circuit = FakeCircuit(identity=identity)
    with pytest.raises(SystemExit):
        run(wizard, monkeypatch, circuit, [""])

    assert circuit.calibrations == []
    config = json.loads(Path(wizard.CONFIG_PATH).read_text())
    assert config["atlas_ph"]["enabled"] is False


def test_failed_mid_point_stops_the_wizard(wizard, monkeypatch) -> None:
    circuit = FakeCircuit(rejected=("Cal,mid,7.00",))
    with pytest.raises(SystemExit):
        run(wizard, monkeypatch, circuit, ["", ""])

    assert circuit.calibrations == ["Cal,mid,7.00"]
    config = json.loads(Path(wizard.CONFIG_PATH).read_text())
    assert config["atlas_ph"]["enabled"] is False


@pytest.mark.parametrize(
    ("rejected", "answers", "sent"),
    [
        ("Cal,low,4.00", ["", "", "", "skip"], ["Cal,mid,7.00", "Cal,low,4.00"]),
        (
            "Cal,high,10.00",
            ["", "", "", ""],
            ["Cal,mid,7.00", "Cal,low,4.00", "Cal,high,10.00"],
        ),
        ("Cal,high,10.00", ["", "", "skip", ""], ["Cal,mid,7.00", "Cal,high,10.00"]),
    ],
)
def test_rejected_optional_point_stops_the_wizard(
    wizard, monkeypatch, rejected: str, answers: list[str], sent: list[str]
) -> None:
    circuit = FakeCircuit(rejected=(rejected,))
    with pytest.raises(SystemExit):
        run(wizard, monkeypatch, circuit, answers)

    assert circuit.calibrations == sent
    config = json.loads(Path(wizard.CONFIG_PATH).read_text())
    assert config["atlas_ph"]["enabled"] is False


def test_point_count_mismatch_does_not_enable(wizard, monkeypatch) -> None:
    circuit = FakeCircuit(reported_points=2)
    with pytest.raises(SystemExit):
        run(wizard, monkeypatch, circuit, ["", "", "skip", "skip"])

    config = json.loads(Path(wizard.CONFIG_PATH).read_text())
    assert config["atlas_ph"]["enabled"] is False
