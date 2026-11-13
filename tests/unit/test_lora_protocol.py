"""Radio-free regression tests for the LoRa transfer protocol."""

from __future__ import annotations

from collections import defaultdict
import base64
import hashlib
import json
from pathlib import Path
import zlib

import pytest

from beamnode.transport.lora import node_send, node_time_request, supervisor_receive


def test_packet_constants_match_prototype2() -> None:
    assert node_send.MAX_PACKET_BYTES == 200
    assert node_send.ACK_TIMEOUT == 20
    assert node_send.MAX_RETRIES == 5
    assert node_send.TX_RX_TURNAROUND == 0.1
    assert supervisor_receive.ACK_REPEATS == 2


def test_data_chunks_fit_packet_limit_and_round_trip() -> None:
    data = bytes(range(256)) * 5
    chunks = node_send.build_chunks_for_limit(
        data,
        file_id="node7_123456789_example",
        node_id="node7",
        run_id="20261113T120000EST",
    )

    assert b"".join(chunks) == data
    total = len(chunks)
    for index, chunk in enumerate(chunks):
        packet = {
            "type": "DATA",
            "f": "node7_123456789_example",
            "n": "node7",
            "r": "20261113T120000EST",
            "i": index,
            "t": total,
            "d": base64.b64encode(chunk).decode(),
        }
        assert len(json.dumps(packet).encode()) <= node_send.MAX_PACKET_BYTES


def test_send_file_retries_data_and_emits_compressed_checksum(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "fixture.json"
    payload = json.dumps({"readings": list(range(80))}).encode()
    source.write_bytes(payload)

    packets: list[dict[str, object]] = []
    attempts: defaultdict[int, int] = defaultdict(int)

    def fake_ack(file_id: str, chunk_index: int, timeout: float):
        assert file_id == "file-id"
        assert timeout == node_send.ACK_TIMEOUT
        attempts[chunk_index] += 1
        if chunk_index == 0 and attempts[chunk_index] == 1:
            return None
        return {"type": "ACK", "i": chunk_index}

    monkeypatch.setattr(node_send, "NODE_ID", "node7")
    monkeypatch.setattr(node_send, "RUN_ID", "run-id")
    monkeypatch.setattr(node_send, "make_file_id", lambda path: "file-id")
    monkeypatch.setattr(node_send, "wait_for_channel_clear", lambda: True)
    monkeypatch.setattr(node_send, "wait_for_ack", fake_ack)
    monkeypatch.setattr(node_send, "send_packet", lambda packet: packets.append(packet.copy()))
    monkeypatch.setattr(node_send, "log", lambda message: None)
    monkeypatch.setattr(node_send.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(node_send.random, "uniform", lambda start, end: 0.0)

    assert node_send.send_file(source) is True

    data_packets = [packet for packet in packets if packet["type"] == "DATA"]
    end_packets = [packet for packet in packets if packet["type"] == "END"]
    assert [packet["i"] for packet in data_packets].count(0) == 2
    assert len(end_packets) == 1
    assert end_packets[0]["checksum"] == hashlib.md5(zlib.compress(payload)).hexdigest()


def test_send_file_stops_after_max_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    packets: list[dict[str, object]] = []

    monkeypatch.setattr(node_send, "make_file_id", lambda path: "file-id")
    monkeypatch.setattr(node_send, "prepare_file", lambda path: (b"compressed", "checksum"))
    monkeypatch.setattr(node_send, "build_chunks_for_limit", lambda *args, **kwargs: [b"chunk"])
    monkeypatch.setattr(node_send, "wait_for_channel_clear", lambda: True)
    monkeypatch.setattr(node_send, "wait_for_ack", lambda *args: None)
    monkeypatch.setattr(node_send, "send_packet", lambda packet: packets.append(packet.copy()))
    monkeypatch.setattr(node_send, "log", lambda message: None)
    monkeypatch.setattr(node_send.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(node_send.random, "uniform", lambda start, end: 0.0)

    assert node_send.send_file("fixture.json") is False
    assert len(packets) == node_send.MAX_RETRIES
    assert {packet["type"] for packet in packets} == {"DATA"}


def test_receiver_acks_and_reassembles_valid_payload(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = json.dumps({"sensor": "bme280", "value": 42}).encode()
    compressed = zlib.compress(payload)
    split = len(compressed) // 2
    chunks = [compressed[:split], compressed[split:]]
    acknowledgements: list[tuple[str, str, int, set[int]]] = []

    supervisor_receive.files.clear()
    supervisor_receive.NODE_OUTPUT_DIRS.clear()
    monkeypatch.setattr(supervisor_receive, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(
        supervisor_receive,
        "send_ack",
        lambda file_id, node_id, index, received: acknowledgements.append(
            (file_id, node_id, index, set(received))
        ),
    )
    monkeypatch.setattr(supervisor_receive, "log", lambda message: None)

    for index in (1, 0):
        supervisor_receive.handle_data(
            {
                "type": "DATA",
                "f": "file-id",
                "n": "node7",
                "r": "run-id",
                "i": index,
                "t": 2,
                "d": base64.b64encode(chunks[index]).decode(),
            }
        )

    supervisor_receive.handle_end(
        {
            "type": "END",
            "f": "file-id",
            "n": "node7",
            "r": "run-id",
            "checksum": hashlib.md5(compressed).hexdigest(),
        }
    )

    received = list(tmp_path.rglob("*.json"))
    assert len(received) == 1
    assert received[0].read_bytes() == payload
    assert acknowledgements[-1] == ("file-id", "node7", 0, {0, 1})
    assert ("node7", "file-id") not in supervisor_receive.files


@pytest.mark.parametrize(
    ("total", "checksum"),
    [
        (2, None),
        (1, "0" * 32),
    ],
)
def test_receiver_keeps_incomplete_or_bad_checksum_transfer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    total: int,
    checksum: str | None,
) -> None:
    compressed = zlib.compress(b"payload")
    supervisor_receive.files.clear()
    supervisor_receive.NODE_OUTPUT_DIRS.clear()
    monkeypatch.setattr(supervisor_receive, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(supervisor_receive, "send_ack", lambda *args: None)
    monkeypatch.setattr(supervisor_receive, "log", lambda message: None)

    supervisor_receive.handle_data(
        {
            "type": "DATA",
            "f": "file-id",
            "n": "node7",
            "r": "run-id",
            "i": 0,
            "t": total,
            "d": base64.b64encode(compressed).decode(),
        }
    )
    supervisor_receive.handle_end(
        {
            "type": "END",
            "f": "file-id",
            "n": "node7",
            "r": "run-id",
            "checksum": checksum or hashlib.md5(compressed).hexdigest(),
        }
    )

    assert not list(tmp_path.rglob("*.json"))
    assert ("node7", "file-id") in supervisor_receive.files


def test_time_request_accepts_time_response(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeRadio:
        def __init__(self) -> None:
            self.sent: list[bytes] = []
            self.responses = [
                json.dumps({"type": "STATUS"}).encode(),
                json.dumps(
                    {"type": "TIME_RESPONSE", "timestamp": "2026-11-13 12:00:00"}
                ).encode(),
            ]

        def send(self, packet: bytes) -> None:
            self.sent.append(packet)

        def receive(self, timeout: float):
            return self.responses.pop(0)

    radio = FakeRadio()
    monkeypatch.setattr(node_time_request.time, "sleep", lambda seconds: None)

    timestamp = node_time_request.request_time(radio, "node7", timeout=1)

    assert timestamp == "2026-11-13 12:00:00"
    assert json.loads(radio.sent[0].decode()) == {
        "type": "TIME_REQUEST",
        "node_id": "node7",
    }
