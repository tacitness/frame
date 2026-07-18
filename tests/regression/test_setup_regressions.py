from __future__ import annotations

import socket
import subprocess
import unittest
from pathlib import Path

from tests.lib.server import FrameServer
from tests.lib.x11 import setup_request


class SetupRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = FrameServer(Path("frame")).start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop()

    def send_invalid(self, request: bytes) -> None:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(2)
        connection.connect(str(self.server.socket_path))
        connection.sendall(request)
        self.assertEqual(connection.recv(1), b"")
        connection.close()
        self.server.assert_running()

    def test_rejects_wrong_protocol_major(self) -> None:
        self.send_invalid(setup_request(major=10))

    def test_rejects_big_endian_clients_without_desynchronizing(self) -> None:
        self.send_invalid(setup_request(byte_order=b"B"))

    def test_auth_tail_can_arrive_with_setup(self) -> None:
        connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        connection.settimeout(2)
        connection.connect(str(self.server.socket_path))
        connection.sendall(setup_request(auth_name=b"MIT", auth_data=b"token"))
        self.assertEqual(connection.recv(1), b"\x01")
        connection.close()

    def test_second_server_cannot_steal_an_active_display(self) -> None:
        contender = subprocess.run(
            [str(self.server.binary), str(self.server.display), "--noinput"],
            cwd=self.server.root,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=2,
        )
        self.assertNotEqual(contender.returncode, 0)
        self.assertIn(b"bind failed", contender.stdout)
        self.assertTrue(self.server.socket_path.is_socket())
        connection, _reply = self.server.connect()
        connection.close()
        self.server.assert_running()


if __name__ == "__main__":
    unittest.main()
