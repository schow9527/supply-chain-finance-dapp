import subprocess

from backend import combined


def test_worker_environment_overrides_web_role(monkeypatch):
    monkeypatch.setenv("PROCESS_ROLE", "web")
    monkeypatch.setenv("EVENT_SYNC_ENABLED", "false")
    monkeypatch.setenv("STORAGE_BACKEND", "render_disk")

    environment = combined._worker_environment()

    assert environment["PROCESS_ROLE"] == "worker"
    assert environment["PROCESS_TYPE"] == "worker"
    assert environment["EVENT_SYNC_ENABLED"] == "true"
    assert environment["STORAGE_BACKEND"] == "disabled"
    assert environment["EVENT_SYNC_BATCH_SIZE"] == "100"
    assert environment["SYNC_POLL_INTERVAL"] == "12"


def test_web_environment_disables_embedded_sync(monkeypatch):
    monkeypatch.setenv("PROCESS_ROLE", "worker")
    monkeypatch.setenv("EVENT_SYNC_ENABLED", "true")

    environment = combined._web_environment()

    assert environment["PROCESS_ROLE"] == "web"
    assert environment["PROCESS_TYPE"] == "web"
    assert environment["EVENT_SYNC_ENABLED"] == "false"


class FakeProcess:
    def __init__(self, return_code=None):
        self.return_code = return_code
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.return_code

    def terminate(self):
        self.terminated = True

    def wait(self, timeout=None):
        if self.return_code is None:
            raise subprocess.TimeoutExpired("fake", timeout)
        return self.return_code

    def kill(self):
        self.killed = True
        self.return_code = -9


def test_stop_children_terminates_and_kills_stuck_processes(monkeypatch):
    process = FakeProcess()
    monkeypatch.setattr(combined.time, "monotonic", lambda: 0.0)

    combined._stop_children([("worker", process)], timeout=0)

    assert process.terminated is True
    assert process.killed is True
