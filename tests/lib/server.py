"""Lifecycle wrapper for an isolated, headless frame process."""

from __future__ import annotations

import os
import secrets
import signal
import socket
import stat
import subprocess
import tempfile
import time
from pathlib import Path

from tests.lib.x11 import SetupReply, receive_setup, setup_request

SOCKET_DIRECTORY = Path("/tmp/.X11-unix")


class FrameServer:
    def __init__(self, binary: Path):
        self.binary = binary.resolve()
        self.root = self.binary.parent
        self.display = self._available_display()
        self.socket_path = self._socket_path(self.display)
        self._home: tempfile.TemporaryDirectory[str] | None = None
        self._log = None
        self.process: subprocess.Popen[bytes] | None = None

    @staticmethod
    def _socket_path(display: int) -> Path:
        return SOCKET_DIRECTORY / f"X{display}"

    @staticmethod
    def _ensure_socket_directory() -> None:
        try:
            SOCKET_DIRECTORY.mkdir(mode=0o1777)
        except FileExistsError:
            if not stat.S_ISDIR(SOCKET_DIRECTORY.lstat().st_mode):
                raise RuntimeError(
                    f"X11 socket path is not a directory: {SOCKET_DIRECTORY}"
                ) from None
        else:
            # mkdir honors the process umask; only chmod a directory we created.
            SOCKET_DIRECTORY.chmod(0o1777)

    @staticmethod
    def _available_display(excluded: set[int] | None = None) -> int:
        excluded = excluded or set()
        minimum = 2000
        span = 50000
        start = secrets.randbelow(span)
        for offset in range(256):
            display = minimum + (start + offset) % span
            if display not in excluded and not FrameServer._socket_path(display).exists():
                return display
        raise RuntimeError("no isolated X11 display number available")

    def start(self) -> "FrameServer":
        self._ensure_socket_directory()
        self._home = tempfile.TemporaryDirectory(prefix="frame-test-home-")
        self._log = tempfile.TemporaryFile()
        attempted: set[int] = set()
        try:
            for attempt in range(10):
                if attempt:
                    self.display = self._available_display(attempted)
                    self.socket_path = self._socket_path(self.display)
                    self._log.seek(0)
                    self._log.truncate()
                attempted.add(self.display)
                environment = os.environ.copy()
                environment.update(
                    {
                        "HOME": self._home.name,
                        "DISPLAY": f":{self.display}",
                        "LC_ALL": "C",
                    }
                )
                self.process = subprocess.Popen(
                    [str(self.binary), str(self.display), "--noinput"],
                    cwd=self.root,
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=self._log,
                    stderr=self._log,
                    start_new_session=True,
                )
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline:
                    if self.process.poll() is not None:
                        output = self.logs()
                        if "bind failed" in output and attempt < 9:
                            break
                        raise RuntimeError(
                            f"frame exited during startup on :{self.display}:\n{output}"
                        )
                    if self.socket_path.is_socket():
                        return self
                    time.sleep(0.01)
                else:
                    raise RuntimeError(
                        f"frame did not create {self.socket_path}:\n{self.logs()}"
                    )
            raise RuntimeError(
                f"frame could not reserve an isolated display after {len(attempted)} attempts"
            )
        except BaseException:
            self._terminate()
            self._close_resources()
            raise

    def connect(self, *, fragmented: bool = False) -> tuple[socket.socket, SetupReply]:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(2)
        connection.connect(str(self.socket_path))
        request = setup_request()
        if fragmented:
            for byte in request:
                connection.sendall(bytes([byte]))
        else:
            connection.sendall(request)
        return connection, receive_setup(connection)

    def assert_running(self) -> None:
        if not self.process or self.process.poll() is not None:
            raise AssertionError(f"frame is not running:\n{self.logs()}")

    def logs(self) -> str:
        if self._log is None:
            return ""
        self._log.flush()
        self._log.seek(0)
        data = self._log.read().decode("utf-8", errors="replace")
        self._log.seek(0, os.SEEK_END)
        return data

    def _terminate(self) -> None:
        if self.process and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=3)

    def _close_resources(self) -> None:
        if self._log is not None:
            self._log.close()
            self._log = None
        if self._home is not None:
            self._home.cleanup()
            self._home = None

    def stop(self) -> None:
        self._terminate()
        stale_socket = self.socket_path.exists()
        self._close_resources()
        if stale_socket:
            raise AssertionError(f"frame left stale socket {self.socket_path}")

    def __enter__(self) -> "FrameServer":
        return self.start()

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.stop()
