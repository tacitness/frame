from __future__ import annotations

import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.lib.server import FrameServer


class ServerHarnessTests(unittest.TestCase):
    def test_socket_directory_is_created_owner_writable_and_sticky(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            socket_dir = Path(tmpdir) / ".X11-unix"
            with patch("tests.lib.server.SOCKET_DIRECTORY", socket_dir):
                FrameServer._ensure_socket_directory()
            self.assertTrue(socket_dir.is_dir())
            self.assertEqual(stat.S_IMODE(socket_dir.stat().st_mode), 0o1777)


if __name__ == "__main__":
    unittest.main()
