#!/usr/bin/env python3
"""End-to-end X11 setup and extension smoke test; never touches hardware."""

from __future__ import annotations

import socket
import stat
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.lib.server import FrameServer  # noqa: E402
from tests.lib.x11 import query_extension, recv_exact  # noqa: E402


class ProtocolSmokeTests(unittest.TestCase):
    binary = ROOT / "frame"

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = FrameServer(cls.binary).start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop()

    def test_fragmented_setup_contract(self) -> None:
        connection, reply = self.server.connect(fragmented=True)
        self.addCleanup(connection.close)
        self.assertEqual((reply.protocol_major, reply.protocol_minor), (11, 0))
        self.assertEqual(reply.vendor, "frame")
        self.assertEqual(reply.roots, 1)
        self.assertEqual(reply.maximum_request_length, 65535)
        self.assertEqual(reply.pixmap_formats, ((24, 32, 32), (32, 32, 32)))

    def test_socket_is_owner_only(self) -> None:
        mode = stat.S_IMODE(self.server.socket_path.stat().st_mode)
        self.assertEqual(mode, 0o700)

    def test_render_extension_is_advertised(self) -> None:
        connection, _reply = self.server.connect()
        self.addCleanup(connection.close)
        connection.sendall(query_extension("RENDER"))
        response = recv_exact(connection, 32)
        self.assertEqual(response[0], 1)
        self.assertEqual(response[8], 1)
        self.assertEqual(response[9], 140)

    def test_unknown_extension_is_absent(self) -> None:
        connection, _reply = self.server.connect()
        self.addCleanup(connection.close)
        connection.sendall(query_extension("FRAME-NOT-REAL"))
        response = recv_exact(connection, 32)
        self.assertEqual(response[0], 1)
        self.assertEqual(response[8:12], b"\0\0\0\0")

    def test_clients_receive_disjoint_resource_ranges(self) -> None:
        first, first_reply = self.server.connect()
        second, second_reply = self.server.connect()
        self.addCleanup(first.close)
        self.addCleanup(second.close)
        self.assertNotEqual(first_reply.resource_id_base, second_reply.resource_id_base)
        self.assertEqual(
            abs(first_reply.resource_id_base - second_reply.resource_id_base), 0x200000
        )

    def test_malformed_client_does_not_kill_server(self) -> None:
        bad = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        bad.settimeout(2)
        bad.connect(str(self.server.socket_path))
        bad.sendall(b"B\0\0\x0b\0\0\0\0\0\0\0\0")
        self.assertEqual(bad.recv(1), b"")
        bad.close()
        self.server.assert_running()
        healthy, reply = self.server.connect()
        healthy.close()
        self.assertEqual(reply.vendor, "frame")


if __name__ == "__main__":
    if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
        ProtocolSmokeTests.binary = Path(sys.argv.pop(1)).resolve()
    unittest.main(verbosity=2)
