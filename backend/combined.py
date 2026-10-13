"""Run the web server and event synchronizer in one Render instance.

This is a small process supervisor for low-traffic deployments where a separate
paid Background Worker is unnecessary. The worker receives role-specific
environment overrides while the web process keeps the production web config.
If either child exits unexpectedly, the supervisor exits so Render restarts the
whole instance instead of leaving event synchronization silently stopped.
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import sys
import time


logger = logging.getLogger(__name__)


def _worker_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        PROCESS_ROLE="worker",
        PROCESS_TYPE="worker",
        EVENT_SYNC_ENABLED="true",
        STORAGE_BACKEND="disabled",
    )
    environment.setdefault("EVENT_SYNC_BATCH_SIZE", "100")
    environment.setdefault("SYNC_POLL_INTERVAL", "12")
    environment.setdefault("PYTHONUNBUFFERED", "1")
    return environment


def _web_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        PROCESS_ROLE="web",
        PROCESS_TYPE="web",
        EVENT_SYNC_ENABLED="false",
    )
    environment.setdefault("PYTHONUNBUFFERED", "1")
    return environment


def _stop_children(children, timeout: float = 10.0) -> None:
    for _name, process in children:
        if process.poll() is None:
            process.terminate()
    deadline = time.monotonic() + timeout
    for _name, process in children:
        if process.poll() is not None:
            continue
        remaining = max(0.0, deadline - time.monotonic())
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def main() -> int:
    logging.basicConfig(level=logging.INFO)
    children = []
    stopping = False

    def request_stop(_signum, _frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)

    try:
        web_process = subprocess.Popen(
            [sys.executable, "-m", "gunicorn", "app:app"],
            env=_web_environment(),
        )
        children.append(("web", web_process))
        worker_process = subprocess.Popen(
            [sys.executable, "-m", "backend.worker"],
            env=_worker_environment(),
        )
        children.append(("event-worker", worker_process))
        logger.info(
            "combined_service_started web_pid=%s worker_pid=%s",
            web_process.pid,
            worker_process.pid,
        )
        while not stopping:
            for name, process in children:
                return_code = process.poll()
                if return_code is not None:
                    logger.error(
                        "combined_child_exited process=%s return_code=%s",
                        name,
                        return_code,
                    )
                    return return_code or 1
            time.sleep(0.5)
        return 0
    finally:
        _stop_children(children)


if __name__ == "__main__":
    raise SystemExit(main())
