"""Start the DocSense backend and frontend together."""

from __future__ import annotations

import signal
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
FRONTEND_DIR = ROOT / "frontend"


def start_process(command: list[str], cwd: Path) -> subprocess.Popen[str]:
    return subprocess.Popen(command, cwd=str(cwd))


def main() -> int:
    backend = start_process([sys.executable, "-m", "uvicorn", "app:app", "--reload"], BACKEND_DIR)
    frontend = start_process(["npm", "run", "dev", "--", "--host", "127.0.0.1", "--port", "3000"], FRONTEND_DIR)

    def shutdown(*_args: object) -> None:
        for process in (frontend, backend):
            if process.poll() is None:
                process.terminate()

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            frontend_exit = frontend.poll()
            backend_exit = backend.poll()

            if frontend_exit is not None or backend_exit is not None:
                break

            time.sleep(0.5)
    except KeyboardInterrupt:
        shutdown()
    finally:
        shutdown()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
