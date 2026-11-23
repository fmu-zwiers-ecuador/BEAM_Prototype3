"""Mocked node-to-supervisor transfer flows for the retry queue."""

from __future__ import annotations

import json
from unittest.mock import Mock

import pytest

from beamnode.supervisor import retryqueue


def configure_flow(tmp_path, monkeypatch, rsync_results: list[bool]):
    state_path = tmp_path / "node_states.json"
    state_path.write_text(
        json.dumps(
            {
                "node1": {
                    "hostname": "bench-node",
                    "ip": "10.42.0.1",
                    "node_state": "unknown",
                    "transfer_fail": False,
                }
            }
        ),
        encoding="utf-8",
    )

    delete = Mock(return_value=True)
    clear = Mock(return_value=True)
    results = iter(rsync_results)

    monkeypatch.setattr(retryqueue, "JSON_FILEPATH", str(state_path))
    monkeypatch.setattr(retryqueue, "JSON_BACKUP_FILEPATH", str(state_path) + ".bak")
    monkeypatch.setattr(retryqueue, "MAX_RETRIES", max(0, len(rsync_results) - 1))
    monkeypatch.setattr(retryqueue, "log", Mock())
    monkeypatch.setattr(retryqueue, "ping_node", lambda _host: True)
    monkeypatch.setattr(retryqueue, "has_remote_data", lambda _host: True)
    monkeypatch.setattr(retryqueue, "backup_remote_shipping_to_usb", lambda _host: True)
    monkeypatch.setattr(retryqueue, "rsync_pull", lambda _host: next(results))
    monkeypatch.setattr(retryqueue, "delete_shipping_data", delete)
    monkeypatch.setattr(retryqueue, "clear_supervisor_data", clear)

    return state_path, delete, clear


@pytest.mark.parametrize(
    ("rsync_results", "expected_calls"),
    [
        ([True], 1),
        ([False, True], 2),
    ],
)
def test_success_and_retry_clear_remote_only_after_transfer(
    tmp_path, monkeypatch, rsync_results, expected_calls
) -> None:
    state_path, delete, clear = configure_flow(tmp_path, monkeypatch, rsync_results)
    rsync = Mock(side_effect=rsync_results)
    monkeypatch.setattr(retryqueue, "rsync_pull", rsync)
    monkeypatch.setattr(retryqueue, "move_to_nas", lambda: True)
    monkeypatch.setattr(retryqueue, "move_to_beamdrive", lambda: True)

    retryqueue.main()

    assert rsync.call_count == expected_calls
    delete.assert_called_once_with("bench-node.local")
    clear.assert_called_once_with()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["node1"]["transfer_fail"] is False


def test_failed_transfer_never_deletes_source_or_staging_data(tmp_path, monkeypatch) -> None:
    state_path, delete, clear = configure_flow(tmp_path, monkeypatch, [False, False])
    monkeypatch.setattr(retryqueue, "move_to_nas", lambda: False)
    monkeypatch.setattr(retryqueue, "move_to_beamdrive", lambda: False)

    retryqueue.main()

    delete.assert_not_called()
    clear.assert_not_called()
    state = json.loads(state_path.read_text(encoding="utf-8"))
    assert state["node1"]["transfer_fail"] is True
