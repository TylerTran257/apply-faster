from __future__ import annotations

import asyncio
import json
import queue
import threading
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse

from ..bootstrap.browser import (
    attach_browser_session,
    cdp_host_from_env,
    cdp_port_from_env,
    resolve_cdp_url,
)
from ..bootstrap.run import execute_run
from .observer import WebObserver
from .state import SessionState

app = FastAPI()

_state = SessionState()
_event_queue: queue.Queue[dict[str, Any]] = queue.Queue()
_session_thread: threading.Thread | None = None

TEMPLATES_DIR = Path(__file__).parent / "templates"


def _run_session() -> None:
    host = cdp_host_from_env()
    port = cdp_port_from_env()
    observer = WebObserver(_state, _event_queue)
    try:
        cdp_url = resolve_cdp_url(host=host, port=port, timeout=10.0)
        with attach_browser_session(cdp_url) as session:
            _summary, csv_path = execute_run(session, observer=observer)
            if csv_path:
                _state.set_complete(
                    _state.to_dict()["summary"] or {},
                    csv_path=str(csv_path),
                )
    except Exception as exc:
        _state.set_error(str(exc))
        _event_queue.put({"type": "error", "error": str(exc)})


@app.get("/")
async def index() -> HTMLResponse:
    template = TEMPLATES_DIR / "index.html"
    if template.exists():
        return HTMLResponse(template.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>applai</h1><p>Web UI not yet installed.</p>")


@app.get("/events")
async def events() -> StreamingResponse:
    async def generate():
        while True:
            try:
                event = _event_queue.get_nowait()
                yield f"data: {json.dumps(event)}\n\n"
            except queue.Empty:
                if _state.status in ("complete", "error", "idle") and _event_queue.empty():
                    await asyncio.sleep(1)
                else:
                    await asyncio.sleep(0.1)

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.get("/api/status")
async def status() -> JSONResponse:
    return JSONResponse(_state.to_dict())


@app.post("/api/start")
async def start_session() -> JSONResponse:
    global _session_thread
    if _state.status == "running":
        return JSONResponse({"error": "Session already running"}, status_code=409)

    _state.reset()
    while not _event_queue.empty():
        try:
            _event_queue.get_nowait()
        except queue.Empty:
            break

    _session_thread = threading.Thread(target=_run_session, daemon=True)
    _session_thread.start()
    return JSONResponse({"status": "started"})


@app.get("/api/csv", response_model=None)
async def download_csv() -> FileResponse | JSONResponse:
    csv_path = _state.to_dict().get("csv_path")
    if not csv_path or not Path(csv_path).exists():
        return JSONResponse({"error": "No CSV available"}, status_code=404)
    return FileResponse(csv_path, filename=Path(csv_path).name, media_type="text/csv")


def start_server(host: str = "0.0.0.0", port: int = 3000) -> None:
    import uvicorn

    uvicorn.run(app, host=host, port=port)
