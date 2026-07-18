from __future__ import annotations

import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class ReleaseToolTests(unittest.TestCase):
    def test_checksum_manifest_replaces_an_existing_artifact_entry(self) -> None:
        with tempfile.TemporaryDirectory(prefix="frame-checksums-") as directory:
            dist = Path(directory)
            first = dist / "first.bin"
            second = dist / "second.bin"
            first.write_bytes(b"first-v1")
            second.write_bytes(b"second")

            command = [
                str(ROOT / "scripts" / "update-checksums.sh"),
                str(dist),
            ]
            subprocess.run(command + [first.name, second.name], check=True)
            first.write_bytes(b"first-v2")
            subprocess.run(command + [first.name], check=True)

            entries = {}
            for line in (dist / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
                digest, name = line.split(maxsplit=1)
                self.assertNotIn(name, entries)
                entries[name] = digest

            self.assertEqual(set(entries), {first.name, second.name})
            self.assertEqual(entries[first.name], hashlib.sha256(b"first-v2").hexdigest())
            self.assertEqual(entries[second.name], hashlib.sha256(b"second").hexdigest())


if __name__ == "__main__":
    unittest.main()
