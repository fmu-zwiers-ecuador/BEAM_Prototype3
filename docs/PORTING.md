# Porting guide

How to move code from `BEAMNode_Prototype2` into this repository. Read this and
[CONTRIBUTING.md](../CONTRIBUTING.md) before starting a porting issue.

## Workflow

1. **Branch.** One branch per issue from the latest `dev`, named
   `<initials>/<issue>-<short-name>` (for example `jr/12-port-bme280`).
2. **Copy first.** Copy the file into its new location in one commit with no
   edits, so review can diff the copy against the original. Then change it in
   later commits.
3. **Change paths.** Replace hard-coded locations with constants from
   `beamnode.paths` (see below). Do not invent new path logic in a script.
4. **Test.** Run `python -m pip install -e ".[dev]"` and `python -m pytest`.
   The guardrail tests in `tests/unit/test_guardrails.py` must pass.
5. **Pull request into `dev`.** Fill in the template, including which bench Pi
   was used for hardware-facing changes. Another developer reviews it; resolve
   every comment, then squash-merge.
6. **Board.** `To Do` → `In progress` → `Need's Testing` (PR open) → `Ready`
   (merged into `dev`) → `Done` (released to `main`).

## Bench-Pi testing

Test hardware-facing ports on a **non-deployed** Pi. Check out your branch at
`/home/pi/BEAM_Prototype3`, run the relevant `tests/hardware/check_*.py`, and
record the node name and attached hardware in the PR. Never commit on a Pi
directly to `dev` or `main`. Deployed systems stay pinned to `main`.

## How scripts find files

All repository locations come from `src/beamnode/paths.py`:

| Constant | Location |
|---|---|
| `REPO_ROOT` | repository root (derived from the file location) |
| `CONFIG_JSON` | `config/config.json` |
| `SENSORS_DIR` | `src/beamnode/sensors/` |
| `LOGS_DIR` | `logs/` |
| `PI_CHECKOUT` | `/home/pi/BEAM_Prototype3` (the Pi checkout path) |

Import them (`from beamnode.paths import CONFIG_JSON`) rather than hard-coding
`/home/pi/...`. Where a legacy wrapper must still reference a Pi path, it must
use `/home/pi/BEAM_Prototype3/...` and the file must exist in this repository
(a guardrail test checks this).

## Configuration

Sprint 1 keeps settings in `config/config.json`. A later milestone moves them to
`/etc/beamnode/` and `/var/lib/beamnode/` and replaces the constants with a
typed `RuntimePaths` object.

## Sensor folders

The scheduler runs `src/beamnode/sensors/<config-section>/<script-name>`, where
`<config-section>` is the section name in `config.json` and `<script-name>` is
its `script_name`. All `atlas_*` sections share the `atlas_sci/` folder
(`paths.sensor_script()` implements this). Every section with a `frequency`
must resolve to an existing script.

## Line endings

`.gitattributes` forces LF for Python, shell, service, timer, configuration,
JSON, TOML, and YAML files. Shell scripts with CRLF fail on the Pi.

## Guardrail tests

`tests/unit/test_guardrails.py` skips areas that are not ported yet and checks:

- Python files under `src/`, `deploy/`, and `tests/hardware/` compile.
- Production code does not mention `BEAMNode_Prototype2`.
- Hard-coded `/home/pi/BEAM_Prototype3/...` paths exist in the repository.
- Every sensor with a `frequency` in `config.json` resolves to a script.
- Shell scripts contain no CRLF line endings.

## CI

CI runs `python -m pytest` on Ubuntu and Windows for pull requests and pushes to
`dev` and `main`. Both jobs should be required checks on both branches (a
repository-settings change; see the issue for status).
