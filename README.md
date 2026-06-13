# python-applai

Standalone Python rewrite of the active CLI-driven LinkedIn Application Review workflow.

## Quick Start (Docker)

The fastest way to get started on any platform (Linux, macOS, Windows).

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed
- Google Chrome installed on your host machine

### Steps

1. **Start Chrome with remote debugging:**

```bash
google-chrome \
  --remote-debugging-port=9222 \
  --remote-debugging-address=0.0.0.0 \
  --user-data-dir=/tmp/chrome-debug \
  --profile-directory="Default" \
  --new-window \
  https://www.linkedin.com/jobs/collections/recommended
```

> `--remote-debugging-address=0.0.0.0` is required so Docker containers can reach Chrome. Without it, Chrome only listens on `127.0.0.1` which is unreachable from inside a container.

2. **Log in to LinkedIn** in the Chrome window that opens.

3. **Start the Docker container:**

```bash
docker compose up
```

4. **Open the web UI** at [http://localhost:3000](http://localhost:3000).

5. **Click "Start Session"** in the web UI to begin reviewing jobs.

### Platform notes

| Platform | CDP networking | Notes |
|----------|---------------|-------|
| macOS | Works out of the box | Docker Desktop resolves `host.docker.internal` natively |
| Windows | Works out of the box | Docker Desktop resolves `host.docker.internal` natively |
| Linux | Works via `extra_hosts` | `docker-compose.yml` includes `host.docker.internal:host-gateway` (Docker 20.10+) |

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CDP_HOST` | `host.docker.internal` | Hostname to reach Chrome from inside Docker |
| `CDP_PORT` | `9222` | Chrome remote debugging port |

Override defaults in your shell or `.env` file:

```bash
CDP_HOST=192.168.1.100 CDP_PORT=9333 docker compose up
```

## Quick Start (pip install)

For users who prefer a local Python setup.

### Setup

```bash
cd apply-faster
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### Run (CLI)

The simplest way to start is with no arguments — Chrome launches automatically:

```bash
applai
```

This will:

1. Launch Chrome with remote debugging enabled
2. Open LinkedIn's recommended jobs page
3. Wait for you to log in and navigate to a jobs page
4. Press Enter in the terminal to begin the review session

### Run (Web UI without Docker)

Start the web UI server locally:

```bash
applai serve
```

Then open [http://localhost:3000](http://localhost:3000). Chrome must be running with `--remote-debugging-port=9222` on the same machine.

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

### First-time setup

Install Chrome and Playwright browser drivers:

```bash
applai setup
```

### CLI options

| Flag | Default | Description |
|------|---------|-------------|
| `--cdp-url` | *(none)* | WebSocket URL for an already-running Chrome session. Skips auto-launch. |
| `--port` | `9222` | Remote debugging port when auto-launching Chrome. |

### Commands

| Command | Description |
|---------|-------------|
| `applai` | Start a CLI review session (auto-launches Chrome) |
| `applai run` | Same as `applai` |
| `applai serve` | Start the web UI server on port 3000 |
| `applai setup` | Install Chrome and Playwright browser drivers |

## Troubleshooting

### Chrome not reachable from Docker

- Verify Chrome is running with `--remote-debugging-port=9222`
- **Ensure Chrome has `--remote-debugging-address=0.0.0.0`** — without this, Chrome only listens on `127.0.0.1` which Docker containers cannot reach
- Test the debug endpoint from your host: `curl http://127.0.0.1:9222/json/version`
- On Linux/WSL2, ensure Docker version is 20.10+ (required for `host-gateway`)
- If `host.docker.internal` doesn't resolve, try your host IP directly: `CDP_HOST=172.17.0.1 docker compose up`

### "No open linkedin.com/jobs tab found"

- Make sure you are on a `linkedin.com/jobs/...` page in Chrome before starting the session
- If Chrome redirected you to `/feed` after login, navigate back to the jobs page manually

### Web UI shows "Error" after clicking Start

- Check the Docker container logs: `docker compose logs`
- Common cause: Chrome is not running or the CDP port is blocked

## Runtime artifacts

- `output/` — Run snapshot files and reviewed-job CSV exports
