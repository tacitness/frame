from __future__ import annotations

import socket
import unittest
from pathlib import Path

from tests.lib.server import FrameServer


INVALID_SETUP_SEEDS = (
    b"\0" * 12,
    b"x\0\x0b\0\0\0\0\0\0\0\0\0",
    b"B\0\0\x0b\0\0\0\0\0\0\0\0",
    b"l\0\x0a\0\0\0\0\0\0\0\0\0",
    b"l\0\xff\xff\0\0\0\0\0\0\0\0",
)


class SetupCorpusTests(unittest.TestCase):
    def test_invalid_corpus_is_contained(self) -> None:
        with FrameServer(Path("frame")) as server:
            for seed in INVALID_SETUP_SEEDS:
                with self.subTest(seed=seed.hex()):
                    connection = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    connection.settimeout(2)
                    connection.connect(str(server.socket_path))
                    connection.sendall(seed)
                    self.assertEqual(connection.recv(1), b"")
                    connection.close()
                    server.assert_running()
            healthy, reply = server.connect()
            healthy.close()
            self.assertEqual(reply.vendor, "frame")


if __name__ == "__main__":
    unittest.main()
