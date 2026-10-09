"""Independent event worker entrypoint: python -m backend.worker."""

import logging
import signal
import threading

from backend.app import create_app
from backend.sync.engine import EventSynchronizer


def main():
    logging.basicConfig(level=logging.INFO)
    app = create_app()
    if not app.config.get("EVENT_SYNC_ENABLED"):
        raise RuntimeError("EVENT_SYNC_ENABLED is false")
    stop_event = threading.Event()

    def stop(_signum, _frame):
        stop_event.set()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    with app.app_context():
        try:
            EventSynchronizer(app).run_forever(stop_event)
        except KeyboardInterrupt:
            stop_event.set()


if __name__ == "__main__":
    main()
