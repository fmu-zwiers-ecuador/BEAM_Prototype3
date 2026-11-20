# Node Shipping (`shipping.py`)

Runs on each node. It prepares the node's collected data so the supervisor can pull it. See [README.md](README.md) for the full pipeline.

## What it does

Moves everything in the node's data folder (`/home/pi/data/`) into the shipping folder (`/home/pi/shipping/`) as a single folder named:

```
data-<node_id>-<UTC timestamp>
```

Example: `data-beam-node-02-20251113T210455Z`

- There is no ZIP or tar archive. One folder is shipped per run.
- The timestamp keeps runs separate, so earlier shipments are never overwritten and no per-node subfolders are needed.
- The supervisor later pulls the contents of `/home/pi/shipping/` with `rsync` and removes them after a successful pull.

## Location and settings

- Script: `/home/pi/BEAM_Prototype3/src/beamnode/storage/shipping.py`
- Settings: `/home/pi/BEAM_Prototype3/config/config.json`

```json
"global": {
    "node_id": "beam-node-02",
    "base_dir": "/home/pi/data",
    "ship_dir": "/home/pi/shipping"
}
```

`node_id` must be unique per node and match the node you are on. It becomes part of every shipped folder name.

## Run

```bash
python3 /home/pi/BEAM_Prototype3/src/beamnode/storage/shipping.py
```

Check the result:

```bash
ls -l /home/pi/shipping
```

## Troubleshooting

**Folder shows the wrong node name.** `node_id` in `config/config.json` on that node is wrong (for example a copied `beam-node-01`). Correct it and ship again.

**Folder shows an old date.** The node's clock is wrong. Pis without network access have no time source and keep drifting. Set the time manually:

```bash
sudo timedatectl set-ntp false
sudo timedatectl set-time "YYYY-MM-DD HH:MM:SS"
date -u
```

**Nothing shipped.** `/home/pi/data/` is empty, or the script could not read `config/config.json`. The supervisor will log `The shipping folder is empty` for that node.

**Supervisor cannot pull.** Walk through "A node is stuck dead or transfer_fail" in [README.md](README.md#recovery).

## Local USB backup

Before the supervisor pulls, it SSHes into the node and copies the shipping folder to the node's USB drive under `shipping_archive/<hostname>-<UTC timestamp>/`. `move_shipping_to_beamdrive.sh` in the same `storage/` directory is the shell helper for this kind of copy. Backup failures are logged to `/home/pi/logs/node_usb_backup.log` and do not stop the transfer.
