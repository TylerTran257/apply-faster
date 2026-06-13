# python-applai

Standalone Python rewrite of the active CLI-driven LinkedIn Application Review workflow.

## Status

This subproject is intended to preserve the active operator workflow from the Node implementation while remaining fully isolated from the rest of the repository.

## Environment

- Target platform: Linux / WSL
- Virtual environment: local `.venv/`

## Setup

```bash
cd apply-faster
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run

The simplest way to start is with no arguments — Chrome launches automatically:

```bash
applai
```

This will:

1. Launch Chrome with remote debugging enabled
2. Open LinkedIn's recommended jobs page
3. Wait for you to log in and navigate to a jobs page
4. Press Enter in the terminal to begin the review session

### Advanced: connect to an existing Chrome session

If you prefer to manage Chrome yourself, pass `--cdp-url` directly:

```bash
# Start Chrome with remote debugging
google-chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-debug \
  --profile-directory="Default" \
  --disable-gpu \
  --disable-software-rasterizer \
  --new-window \
  https://www.linkedin.com/jobs/collections/recommended

# Get the WebSocket URL
curl http://127.0.0.1:9222/json/version

# Connect
applai --cdp-url "ws://127.0.0.1:9222/devtools/browser/<id>"
```

### CLI options

| Flag | Default | Description |
|------|---------|-------------|
| `--cdp-url` | *(none)* | WebSocket URL for an already-running Chrome session. Skips auto-launch. |
| `--port` | `9222` | Remote debugging port when auto-launching Chrome. |

## Runtime artifacts

- `output/` — Run snapshot files and reviewed-job CSV exports
