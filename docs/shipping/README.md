# BEAM Shipping and Queue System

How data moves from the sensor nodes to the supervisor, and from the supervisor to long-term storage.

Related docs: [node-shipping.md](node-shipping.md) (node side), [bench-test.md](bench-test.md) (test procedure), [retry-queue.md](retry-queue.md) (retry logic).

## Overview

A central **Supervisor Raspberry Pi** collects data from **node** Pis over the BATMAN mesh (nodes are reached as `nodeX.local`).

1. Each node moves its collected data into `/home/pi/shipping/` as one folder named `data-<node_id>-<UTC timestamp>` (see [node-shipping.md](node-shipping.md)).
2. The supervisor pings every node every 10 minutes and records alive/dead state in `config/node_states.json`.
3. Once a day (19:00) the supervisor runs `retryqueue.py`, which for each active node:
   - backs up the node's shipping folder to the node's own USB drive (a failed backup only logs a warning),
   - pulls the folder with `rsync` into `/home/pi/usbmnt/data/` on the supervisor,
   - deletes the node's shipping folder after a successful pull,
   - retries failed or offline nodes for up to 5 rounds.
4. After the node loop, the supervisor copies `/home/pi/usbmnt/data/` to the NAS and to the local BEAMdrive. **Only if both succeed** is `/home/pi/usbmnt/data/` cleared.

Only `node1`, `node2` and `node3` are processed (`ACTIVE_NODE_NAMES` in `retryqueue.py`). The other entries in `node_states.json` are skipped.

## File locations (Prototype3)

The repository is checked out at `/home/pi/BEAM_Prototype3` on every Pi.

| Purpose | Path |
|---|---|
| Node shipping script | `src/beamnode/storage/shipping.py` |
| Node USB backup helper | `src/beamnode/storage/move_shipping_to_beamdrive.sh` |
| Supervisor ping script | `src/beamnode/supervisor/ping_nodes_10min.py` |
| Supervisor queue script | `src/beamnode/supervisor/retryqueue.py` |
| Retry shell logic | `src/beamnode/supervisor/retrylogic.sh` |
| Supervisor BEAMdrive copy | `src/beamnode/supervisor/move_supervisor_data_to_beamdrive.sh` |
| Node state file | `config/node_states.json` |
| Node settings | `config/config.json` |
| NAS setting | `.env` in the repo root (`NAS_PATH`) |

Runtime locations on the Pis:

| What | Path |
|---|---|
| Node data being collected | `/home/pi/data/` |
| Node shipping folder | `/home/pi/shipping/` |
| Supervisor landing folder (on USB `/dev/sda1`) | `/home/pi/usbmnt/data/` |
| Supervisor queue log | `/home/pi/logs/queue.log` |
| Supervisor ping log | `/home/pi/logs/ping.log` |
| Node USB backup log | `/home/pi/logs/node_usb_backup.log` (on each node) |

## Node state file

`config/node_states.json` is committed with every node set to `dead` / `transfer_fail: true`. The scripts update it at runtime:

```json
"node3": {
    "ip": "10.42.0.3",
    "hostname": "node3.local",
    "node_state": "dead",
    "transfer_fail": true
}
```

- `ping_nodes_10min.py` updates `node_state` (alive/dead).
- `retryqueue.py` updates `node_state` and `transfer_fail`.

Writes are atomic (temp file, fsync, rename), and the previous good copy is kept as `config/node_states.json.bak`. Both the `.bak` file and the temp files are git-ignored. Because the live file is tracked, `git status` on a supervisor will show it as modified after a run. That is expected.

## Installation (supervisor)

```bash
cd /home/pi/BEAM_Prototype3
python3 -m venv .venv
.venv/bin/pip install -e .
```

`retryqueue.py` imports `beamnode.paths` and `python-dotenv`, so it must be run with the interpreter that has the package installed. Create `/home/pi/BEAM_Prototype3/.env`:

```
NAS_PATH=user@nas-host
```

The script appends `:/BEAM_test_data/FEC/` to this value to form the `scp` destination.

Cron entries (install as user `pi`, never with sudo):

```
*/10 * * * * /home/pi/BEAM_Prototype3/.venv/bin/python /home/pi/BEAM_Prototype3/src/beamnode/supervisor/ping_nodes_10min.py
0 19 * * * /home/pi/BEAM_Prototype3/.venv/bin/python /home/pi/BEAM_Prototype3/src/beamnode/supervisor/retryqueue.py
```

Check with `crontab -l`. To run the queue by hand:

```bash
/home/pi/BEAM_Prototype3/.venv/bin/python /home/pi/BEAM_Prototype3/src/beamnode/supervisor/retryqueue.py
```

## Recovery

Start with the log: `tail -n 100 /home/pi/logs/queue.log`.

### `node_states.json` is missing, empty or corrupt

Log lines: `node state file missing` or `Could not read JSON (...)`.

- The script automatically falls back to `config/node_states.json.bak` and rewrites the primary file ("Recovered node state from backup").
- If the backup is also unusable, the log says `Backup also unusable ... Starting with empty node state` and the run ends without transferring anything. Restore the committed copy:
  ```bash
  cd /home/pi/BEAM_Prototype3
  git checkout -- config/node_states.json
  ```
  This resets every node to `dead`. The next ping run (within 10 minutes) refreshes the states.

### Supervisor USB is not mounted or not writable

Log lines: `Mounting /dev/sda1 ...`, `Could not create ...`, or a warning that the path is on a `vfat`/`exfat` filesystem and not writable.

1. Check the mount: `findmnt /home/pi/usbmnt` and `ls -ld /home/pi/usbmnt/data`.
2. The script tries a remount with `uid`/`gid`/`umask` for user `pi`. On FAT/exFAT drives `chown` cannot work, so the mount options must be fixed.
3. Run the USB permissions script once with sudo: `set_node_usb_backup_permissions.sh` (it also updates `/etc/fstab` so the fix survives reboots).

### NAS backup fails

- `ERROR: NAS_PATH is not set`: add `NAS_PATH` to `/home/pi/BEAM_Prototype3/.env`.
- `NAS BACKUP FAILED` with `scp stderr`: check network access to the NAS and that SSH keys are set up for user `pi`.
- In both cases the supervisor data is **not** cleared (`WARNING: Did not clear supervisor data`). Nothing is lost; the next run retries the NAS copy.

### BEAMdrive copy fails

Log line: `Move To BEAMDrive ERROR`. Check that the drive is attached and that `move_supervisor_data_to_beamdrive.sh` exists and uses LF line endings (`file` should not report CRLF). Supervisor data is not cleared until this succeeds.

### A node is stuck `dead` or `transfer_fail: true`

1. `ping -c 3 nodeX.local` from the supervisor.
2. `ssh -o BatchMode=yes pi@nodeX.local ls /home/pi/shipping`. `BatchMode` means key-based login is required; a password prompt counts as a failure.
3. If the shipping folder is empty, the node has nothing to send (`The shipping folder is empty`). Check that `shipping.py` ran on the node.
4. A failed pull leaves the node's shipping folder untouched, so the next daily run (or the next retry round) tries again.
5. If the node's USB backup fails (`USB backup failed; continuing supervisor pull anyway`), the pull still proceeds. Look at `/home/pi/logs/node_usb_backup.log` on the node.
6. If the remote cleanup fails, the script attempts a `chown`/`chmod` repair over SSH once. If the node needs a sudo password, fix that on the node manually.

### Disk full

State-file writes are atomic, so a full disk no longer leaves an empty `node_states.json`. Free space on the Pi, then rerun.

## Notes

- Do not run cron setup with sudo; the jobs must belong to user `pi`.
- Keep `config/node_states.json` writable by `pi`.
- Shell scripts must use LF line endings. CI fails on CRLF.
