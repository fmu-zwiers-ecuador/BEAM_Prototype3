# Supervisor retry queue

The supervisor shipping workflow pulls node data over the BATMAN mesh, records
transfer state, retries failed nodes, and stages successful transfers for the
NAS. The runtime scripts are:

- `src/beamnode/supervisor/ping_nodes_10min.py`
- `src/beamnode/supervisor/retryqueue.py`
- `src/beamnode/supervisor/retrylogic.sh`
- `src/beamnode/supervisor/move_supervisor_data_to_beamdrive.sh`

Service and timer installation is tracked separately in issue #11. Do not add a
second cron schedule for a workflow already managed by systemd.

## Runtime paths

| Purpose | Path |
|---|---|
| Node state | `config/node_states.json` |
| Node shipping source | `/home/pi/shipping` |
| Supervisor staging root | `/home/pi/usbmnt/data` |
| Queue log | `/home/pi/logs/queue.log` |
| NAS transfer helper | `src/beamnode/supervisor/move_supervisor_data_to_beamdrive.sh` |

The supervisor must run from an installed Prototype3 checkout so the shared
`beamnode.paths` constants resolve to that checkout. Set the NAS host and other
deployment-specific values in the environment; missing NAS configuration is
reported when the NAS operation runs rather than crashing module import.

## Manual operation

From the Prototype3 repository root:

```bash
python3 src/beamnode/supervisor/ping_nodes_10min.py
python3 src/beamnode/supervisor/retryqueue.py
```

Use only a disposable bench node for an end-to-end run. Follow
[`bench-test.md`](bench-test.md) and retain the source checksum, destination
checksum, and matching `queue.log` entries as evidence.

## Recovery

1. Inspect `/home/pi/logs/queue.log` for the node name and failed step.
2. Confirm the node address and transfer state in `config/node_states.json`.
3. Verify the supervisor can reach the node over the BATMAN mesh.
4. Confirm `/home/pi/usbmnt` is mounted and has enough free space.
5. Correct the failed dependency, then rerun `retryqueue.py`.
6. Compare source and destination checksums before clearing or replacing any
   source data.

Do not delete a node's shipping directory merely because `rsync` returned
success; the known reliability work is tracked separately and requires transfer
verification before deletion behavior changes.
