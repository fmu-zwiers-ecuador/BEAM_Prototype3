# LoRa sending protocol

BEAM nodes without mesh networking use RFM9x radios to request time and send
compressed JSON files to a supervisor. The implementation lives in
`src/beamnode/transport/lora/` and preserves the Prototype2 protocol while the
reliability follow-ups in issues #22 and #23 remain blocked on the port.

## Roles and entry points

| Role | Entry point | Purpose |
|---|---|---|
| Node | `node_time_request.py` | Request the supervisor's current time and set the node clock |
| Node | `node_send.py` | Compress and send JSON files in acknowledged chunks |
| Supervisor | `supervisor_receive.py` | Answer time requests, acknowledge chunks, validate files, and save them |

All radios use 915 MHz, CE1 for chip select, GPIO 25 for reset, and transmit
power 23. The scripts require the packages listed in
`deploy/setup/lora_packages.txt`.

## Transfer identifiers

The node takes its hostname as `node_id`. Each sender run also has a timestamped
`run_id`. Every file gets a `file_id` made from the node ID, a nanosecond
timestamp, and a sanitized form of the source filename.

Together, `node_id` and `file_id` identify the supervisor's in-memory transfer.
The `run_id` groups received files into one supervisor output directory.

## Packets

Packets are UTF-8 JSON and must serialize to no more than 200 bytes.

### DATA

```json
{
  "type": "DATA",
  "f": "node7_..._reading",
  "n": "node7",
  "r": "20261113T120000EST",
  "i": 0,
  "t": 4,
  "d": "eJyrVkrLz1ey..."
}
```

- `f`: file ID
- `n`: node ID
- `r`: sender run ID
- `i`: zero-based chunk index
- `t`: total chunk count
- `d`: base64-encoded compressed bytes for this chunk

The sender calculates the largest chunk size that keeps even the final DATA
packet within the 200-byte serialized limit.

### ACK

```json
{
  "type": "ACK",
  "f": "node7_..._reading",
  "n": "node7",
  "i": 0,
  "received": [0]
}
```

The sender accepts an ACK only when its type, file ID, node ID, and chunk index
match the packet currently awaiting acknowledgement. `received` records all
chunk indexes held by the supervisor, but the current sender does not use it
for selective retransmission.

### END

```json
{
  "type": "END",
  "f": "node7_..._reading",
  "n": "node7",
  "r": "20261113T120000EST",
  "checksum": "d41d8cd98f00b204e9800998ecf8427e"
}
```

The checksum is MD5 over the complete **compressed** payload, not over the
original JSON bytes. On END, the supervisor requires every chunk, joins them in
index order, validates that checksum, decompresses the result, and writes the
original bytes.

The current protocol does not acknowledge END. See issue #22 before changing
that behavior.

### TIME_REQUEST and TIME_RESPONSE

```json
{"type": "TIME_REQUEST", "node_id": "node7"}
```

```json
{"type": "TIME_RESPONSE", "timestamp": "2026-11-13 12:00:00"}
```

The supervisor waits four seconds before responding so the node can switch to
receive mode. The node waits up to 300 seconds and applies the response with
`sudo date -s`. The installer writes the required date command to
`/etc/sudoers.d/beamnode-date`; the Python script itself never runs as root.
When executed by absolute path, the script adds the checkout's `src` directory
to its import path before loading `beamnode.paths`.

## Retry and collision behavior

The port preserves these settings:

| Setting | Value |
|---|---:|
| Maximum serialized packet | 200 bytes |
| ACK timeout | 20 seconds |
| Attempts per DATA chunk | 5 |
| TX-to-RX turnaround | 0.1 seconds |
| Initial per-file jitter | 0-10 seconds |
| Retry backoff base / cap | 0.25 / 4 seconds |
| Inter-chunk jitter | 0-0.35 seconds |
| Supervisor ACK repeats | 2 |
| ACK repeat gap | 0.08 seconds |

Before transmitting, the sender samples the channel for activity. A missing
ACK causes exponential randomized backoff. A chunk that exhausts all five
attempts fails the file; the caller moves that file to the configured storage
directory.

## Supervisor output

The default supervisor output root is `/home/pi/data`. Files from one node and
run are grouped under:

```text
/home/pi/data/node<node-number>_loradata_<run-id>/
```

The output filename is `<node-number>_<file-id>.json`. If a node ID has no
digits, a sanitized node ID is used instead.

## Installation

From `/home/pi/BEAM_Prototype3` on each non-deployed Pi:

```bash
python3 -m pip install -r deploy/setup/lora_packages.txt
python3 -m pip install -e .
```

Install the appropriate role:

```bash
sudo bash deploy/setup/install_lora_automation.sh node
sudo bash deploy/setup/install_lora_automation.sh supervisor
```

The node role installs `lora-node-send.service` and a timer whose schedule is
read from `config/config.json`. The supervisor role installs the continuously
running `lora-supervisor-receive.service`. Both services execute from
`/home/pi/BEAM_Prototype3` with `PYTHONPATH` set to the repository's `src`
directory.

Useful status commands:

```bash
systemctl status lora-node-send.timer lora-node-send.service --no-pager
systemctl status lora-supervisor-receive.service --no-pager
journalctl -u lora-supervisor-receive.service --since today --no-pager
```

## Bench verification

Use two non-deployed Pis and disposable data only.

1. Record the node and supervisor hostnames and attached RFM9x hardware.
2. Install the node and supervisor roles and confirm both units use Prototype3
   paths with `systemctl cat`.
3. Start the supervisor receiver.
4. Create one uniquely named JSON fixture on the node and retain a copy outside
   the sender's scan directory.
5. Record the original byte count, SHA-256, and MD5 of its zlib-compressed
   bytes.
6. Run the sender and record its exit status, DATA retry count, and log.
7. Find the supervisor output, compare it byte-for-byte with the retained
   source, and record its SHA-256.
8. Run `node_time_request.py`, record the node time before and after, and retain
   the node and supervisor time-request logs.

The automated protocol tests use fake radios and run without Raspberry Pi
hardware:

```bash
python -m pytest -q tests/unit/test_lora_paths.py tests/unit/test_lora_protocol.py
```

## Known limitations

- END is not acknowledged, so a node can delete a source that the supervisor
  never finalized. Tracked in #22.
- The sender recursively selects every JSON file under its configured root and
  can remove files owned by other workflows. Tracked in #23.
- The receiver does not yet validate radio-supplied run and file identifiers
  before building output paths. Tracked in #25.
- Transfers exist only in supervisor memory until they are finalized; a
  receiver restart discards partial transfer state.

Do not silently fix these behaviors in a path-only port. Change them in their
own reviewed issues with mixed-version and two-radio evidence.
