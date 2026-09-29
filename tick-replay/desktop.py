"""Tick Replay desktop program.

Starts the local server and opens the site in its own app window (Microsoft Edge or
Google Chrome in "app" mode: no tabs or address bar). Closing the window quits the program.

    python desktop.py              # from source
    TickReplay.exe                 # the packaged Windows build (see TickReplay.spec)

Data lives in a "data" folder next to the program. Demo data is created on first start.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
from pathlib import Path

FROZEN = getattr(sys, "frozen", False)
APP_DIR = Path(sys.executable).parent if FROZEN else Path(__file__).resolve().parent
RES_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
DATA_DIR = Path(os.environ.get("TICK_DATA_DIR", APP_DIR / "data" / "ticks"))
PROFILE_DIR = APP_DIR / "data" / "window"
LOG_FILE = APP_DIR / "data" / "tick-replay.log"
PORT = 47291            # fixed so a second start finds the running copy
IDLE_QUIT_SEC = 150     # quit when no open page has pinged for this long (hidden tabs ping ~1/min)

os.environ["TICK_DATA_DIR"] = str(DATA_DIR)
os.environ["TICK_WEB_DIR"] = str(RES_DIR / "web")
sys.path.insert(0, str(RES_DIR))

log = logging.getLogger("tick-replay")


def setup_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    handlers = [logging.FileHandler(LOG_FILE, encoding="utf-8")]
    if sys.stderr is not None:
        handlers.append(logging.StreamHandler())
    else:  # windowed build: there is no console, send stray prints to the log
        sys.stdout = sys.stderr = open(LOG_FILE, "a", encoding="utf-8", buffering=1)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", handlers=handlers)


def already_running(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ping", timeout=1) as r:
            return json.load(r).get("ok") is True
    except Exception:
        return False


def port_free(port: int) -> bool:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def find_app_browser() -> str | None:
    """Edge ships with Windows 10/11; Chrome is the fallback."""
    candidates = []
    for env in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
        base = os.environ.get(env)
        if base:
            candidates += [Path(base) / "Microsoft/Edge/Application/msedge.exe",
                           Path(base) / "Google/Chrome/Application/chrome.exe"]
    for c in candidates:
        if c.exists():
            return str(c)
    for name in ("msedge", "google-chrome", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return None


def open_window(url: str) -> subprocess.Popen | None:
    browser = find_app_browser()
    if browser:
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        log.info("opening app window with %s", browser)
        return subprocess.Popen([
            browser, f"--app={url}", f"--user-data-dir={PROFILE_DIR}",
            "--window-size=1500,900", "--no-first-run", "--no-default-browser-check",
        ])
    log.info("no Edge/Chrome found, opening default browser")
    webbrowser.open(url)
    return None


def ensure_demo_data() -> None:
    if DATA_DIR.exists() and any(p.is_dir() for p in DATA_DIR.iterdir()):
        return
    from tools.make_sample import generate

    log.info("creating demo data in %s", DATA_DIR)
    generate(DATA_DIR)


def main() -> None:
    setup_logging()
    no_window = "--no-window" in sys.argv

    if already_running(PORT):
        log.info("already running, opening another window")
        if not no_window:
            open_window(f"http://127.0.0.1:{PORT}/")
        return

    import uvicorn

    from server import app as server_app

    port = PORT if port_free(PORT) else free_port()
    url = f"http://127.0.0.1:{port}/"
    server = uvicorn.Server(uvicorn.Config(server_app.app, host="127.0.0.1", port=port,
                                           log_config=None, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.05)
    log.info("server running at %s (data: %s)", url, DATA_DIR)

    # demo data in the background; the start page shows a notice until it is ready
    threading.Thread(target=ensure_demo_data, daemon=True).start()

    proc = None if no_window else open_window(url)
    opened = time.monotonic()
    try:
        while not server.should_exit:
            time.sleep(1)
            if proc is not None and proc.poll() is not None:
                if time.monotonic() - opened > 5:
                    log.info("window closed")
                    break
                proc = None  # handed off to an already running browser; rely on pings instead
            last = server_app.last_ping["t"]
            if last and time.monotonic() - last > IDLE_QUIT_SEC:
                log.info("no open pages, quitting")
                break
    except KeyboardInterrupt:
        pass
    server.should_exit = True
    time.sleep(0.5)


if __name__ == "__main__":
    main()
