# BEAM Prototype3

BEAM sensor node and supervisor software, rebuilt according to the repository
overhaul plan.

## Repository layout

```text
BEAM_Prototype3/
├── .github/             Pull request template and CI
├── config/              Versioned example configuration
├── deploy/              systemd, Ansible, and network deployment assets
├── docs/                Documentation organized by topic
├── legacy/              Retired code kept only for reference
├── logs/                Runtime log directory; contents are ignored
├── src/beamnode/        Installable Python package
└── tests/               Unit, integration, and manual hardware checks
```

This branch establishes the target structure. Production behavior will move
into it through small, reviewed pull requests as described by the overhaul
plan.

## Development

Install the project and its development tools, then run the test suite:

```bash
python -m pip install -e ".[dev]"
python -m pytest
```

See [CONTRIBUTING.md](CONTRIBUTING.md) before starting work.
