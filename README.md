# python-applai

Standalone Python rewrite of the active CLI-driven LinkedIn Application Review workflow.

## Status

This subproject is intended to preserve the active operator workflow from the Node implementation while remaining fully isolated from the rest of the repository.

## Environment

- Target platform: Linux / WSL
- Dependency manager: `uv`
- Virtual environment: local `.venv/`

## Setup

```bash
cd python-applai
uv sync
source .venv/bin/activate
```

## Run

```bash
applai --cdp-url "<ws://...>"
```

## Operator contract

- Chrome is started externally by the operator
- Remote debugging is already enabled
- The operator already has a logged-in LinkedIn jobs tab open
- The CLI receives only `--cdp-url`

## Runtime artifacts

- `output/` — Run snapshot files
- `logs/` — main logs and per-posting application-entry artifacts
