# Bench Test: Nodes and Supervisor

Procedure for testing the full shipping and queue path on the bench. See [README.md](README.md) for how the system works and [node-shipping.md](node-shipping.md) for the node side.

Original test by Alexander Lance (Nov 2025, reviewed by Dr. Paul Zwiers and Raiz Mohammed). Updated for Prototype3 paths and the current `retryqueue.py`.

## Setup

- Supervisor Raspberry Pi and at least one node (`node1`, `node2` or `node3`), on the same network. Wi-Fi is not required.
- The Prototype3 repository checked out at `/home/pi/BEAM_Prototype3` on every Pi. With no Wi-Fi, copy updates to the supervisor by USB drive and `rsync` them from the supervisor to each node.
- On the supervisor: package installed (`.venv/bin/pip install -e .`) and `.env` created (see [README.md](README.md#installation-supervisor)).
- Passwordless SSH from the supervisor to each node (`ssh -o BatchMode=yes pi@node1.local true` must succeed).
- Correct clocks on all Pis (`date -u`).

## Procedure

**1. Confirm the node's identity.** In `/home/pi/BEAM_Prototype3/config/config.json` on the node, check that `node_id` matches that node.

**2. Put test data on the node.**

```bash
mkdir -p /home/pi/data
echo test > /home/pi/data/test.txt
```

**3. Ship on the node.**

```bash
python3 /home/pi/BEAM_Prototype3/src/beamnode/storage/shipping.py
ls -l /home/pi/shipping
```

Expected: a folder like `data-beam-node-02-20251113T210455Z`.

**4. Check from the supervisor.**

```bash
ping -c 3 node2.local
ssh pi@node2.local 'ls -l /home/pi/shipping'
```

**5. Run the queue on the supervisor.** To inspect the pulled data afterwards, leave `NAS_PATH` unset for this test. The NAS step then fails and the supervisor deliberately does not clear `/home/pi/usbmnt/data/`. (If the NAS and BEAMdrive copies both succeed, the folder is cleared.)

```bash
/home/pi/BEAM_Prototype3/.venv/bin/python \
  /home/pi/BEAM_Prototype3/src/beamnode/supervisor/retryqueue.py
```

**6. Verify.**

```bash
tail -n 50 /home/pi/logs/queue.log
ls -1 /home/pi/usbmnt/data
ls -l /home/pi/usbmnt/data/<newest folder>/
```

## Pass criteria

- Step 3 creates a correctly named and dated folder in `/home/pi/shipping/`.
- Step 5 logs `TRANSFER SUCCESS` for the node, and the folder appears in `/home/pi/usbmnt/data/` with the same contents.
- The node's `/home/pi/shipping/` is empty afterwards (`Remote folder cleared`).
- Repeating steps 2 to 5 adds a new timestamped folder and does not overwrite earlier ones.
- The node's USB drive has a new `shipping_archive/<hostname>-<timestamp>/` folder.

## Also test the failure paths

- Power off a node: it should be logged `OFFLINE`, marked `dead` in `config/node_states.json`, and retried up to 5 rounds.
- Unset `NAS_PATH` with data present: the log shows the missing-configuration error and `Did not clear supervisor data`.
- Empty `config/node_states.json`: the script recovers from `config/node_states.json.bak` (see [README.md](README.md#recovery)).

## Lessons from the original test

- The shipped folders had the wrong node name because `node_id` in the node's config was left at `beam-node-01`. Always confirm it per node.
- Folders carried September dates because the node's clock was wrong. Set the clock manually on offline Pis.
- The design is folder-based: the node ships one folder per run and the timestamp in its name separates runs. An earlier assumption of ZIP files and per-node, per-timestamp subfolders on the supervisor was wrong.
- Verify design assumptions with the supervisor before changing logic.

## References

- rsync manual: https://linux.die.net/man/1/rsync
- Raspberry Pi forums: https://forums.raspberrypi.com/
