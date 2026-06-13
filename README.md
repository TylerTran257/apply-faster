# python-applai

Standalone Python rewrite of the active CLI-driven LinkedIn Application Review workflow.

## Quick Start

### 1. Install

```bash
cd apply-faster
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

First-time setup (installs Chrome and Playwright browser drivers if needed):

```bash
applai setup
```

### 2. Run

```bash
applai serve
```

This will:

1. Auto-launch Chrome and open LinkedIn's recommended jobs page
2. Start the web UI server on port 3000
3. You log in to LinkedIn in the Chrome window
4. Open [http://localhost:3000](http://localhost:3000) and click **Start Session**
5. Review jobs by closing tabs — close quickly to skip, leave open to mark as reviewed
6. When done, download the reviewed-jobs CSV from the web UI

## Docker Setup

For cross-platform distribution or if you prefer not to install Python locally.

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) installed
- Google Chrome installed on your host machine

### Steps

1. **Start Chrome with remote debugging** (in a separate terminal):

**Linux / macOS:**

```bash
google-chrome \
  --remote-debugging-port=9222 \
  --remote-debugging-address=0.0.0.0 \
  --user-data-dir=/tmp/chrome-debug \
  --profile-directory="Default" \
  --new-window \
  https://www.linkedin.com/jobs/collections/recommended
```

**Windows (Command Prompt):**

```cmd
"C:\Program Files\Google\Chrome\Application\chrome.exe" ^
  --remote-debugging-port=9222 ^
  --remote-debugging-address=0.0.0.0 ^
  --user-data-dir=%TEMP%\chrome-debug ^
  --profile-directory="Default" ^
  --new-window ^
  https://www.linkedin.com/jobs/collections/recommended
```

**Windows (PowerShell):**

```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --remote-debugging-address=0.0.0.0 `
  --user-data-dir=$env:TEMP\chrome-debug `
  --profile-directory="Default" `
  --new-window `
  https://www.linkedin.com/jobs/collections/recommended
```

> `--remote-debugging-address=0.0.0.0` is required so Docker containers can reach Chrome. Without it, Chrome only listens on `127.0.0.1` which is unreachable from inside a container.

2. **Log in to LinkedIn** in the Chrome window that opens.

3. **Build and start the container:**

```bash
docker compose up --build
```

4. **Open** [http://localhost:3000](http://localhost:3000) and click **Start Session**.

### Platform notes

| Platform | CDP networking | Notes |
|----------|---------------|-------|
| macOS | Works out of the box | Docker Desktop resolves `host.docker.internal` natively |
| Windows | Works out of the box | Docker Desktop resolves `host.docker.internal` natively |
| Linux / WSL2 | Works via `extra_hosts` | `docker-compose.yml` includes `host.docker.internal:host-gateway` (Docker 20.10+) |

### Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CDP_HOST` | `host.docker.internal` | Hostname to reach Chrome from inside Docker |
| `CDP_PORT` | `9222` | Chrome remote debugging port |

Override defaults in your shell or `.env` file:

```bash
CDP_HOST=192.168.1.100 CDP_PORT=9333 docker compose up
```

## Alternative: CLI-only mode

If you prefer terminal output over the web UI:

```bash
applai
```

Chrome auto-launches. Log in to LinkedIn, press Enter in the terminal to begin, and review jobs by closing tabs. Session summary prints to the terminal.

To connect to an already-running Chrome instead of auto-launching:

```bash
applai --cdp-url "ws://127.0.0.1:9222/devtools/browser/<id>"
```

## Commands

| Command | Description |
|---------|-------------|
| `applai` | Start a CLI review session (auto-launches Chrome) |
| `applai run` | Same as `applai` |
| `applai serve` | Start the web UI server on port 3000 (auto-launches Chrome locally) |
| `applai setup` | Install Chrome and Playwright browser drivers |

| Flag | Default | Description |
|------|---------|-------------|
| `--cdp-url` | *(none)* | WebSocket URL for an already-running Chrome session. Skips auto-launch. |
| `--port` | `9222` | Remote debugging port when auto-launching Chrome. |

## Troubleshooting

### Chrome not reachable from Docker

- Verify Chrome is running with `--remote-debugging-port=9222`
- **Ensure Chrome has `--remote-debugging-address=0.0.0.0`** — without this, Chrome only listens on `127.0.0.1` which Docker containers cannot reach
- Test the debug endpoint from your host: `curl http://127.0.0.1:9222/json/version`
- On Linux/WSL2, ensure Docker version is 20.10+ (required for `host-gateway`)
- If `host.docker.internal` doesn't resolve, try your host IP directly: `CDP_HOST=172.17.0.1 docker compose up`

### "No open linkedin.com/jobs tab found"

- Make sure you are on a `linkedin.com/jobs/...` page in Chrome before starting the session
- If Chrome redirected you to `/feed` after login, the tool will try to navigate automatically — if it still fails, navigate manually

### Web UI shows "Waiting for Chrome..."

- Chrome may still be starting up — wait a few seconds
- If it persists, check that Chrome launched successfully (look for the Chrome window)
- For Docker: ensure Chrome is running on the host with the debug flags above

### Web UI shows "Error" after clicking Start

- Check logs: `docker compose logs` (Docker) or the terminal running `applai serve` (local)
- Common cause: Chrome is not running or the CDP port is blocked

## Runtime artifacts

- `output/` — Run snapshot files and reviewed-job CSV exports
