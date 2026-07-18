from __future__ import annotations

import struct
import unittest

from tests.lib.x11 import pad4, query_extension, setup_request


class X11CodecTests(unittest.TestCase):
    def test_padding_is_four_byte_aligned(self) -> None:
        self.assertEqual(
            [pad4(value) for value in range(9)], [0, 4, 4, 4, 4, 8, 8, 8, 8]
        )

    def test_little_endian_setup_header(self) -> None:
        request = setup_request()
        self.assertEqual(len(request), 12)
        self.assertEqual(request[:2], b"l\0")
        self.assertEqual(struct.unpack_from("<HHHH", request, 2), (11, 0, 0, 0))

    def test_setup_auth_fields_are_independently_padded(self) -> None:
        request = setup_request(auth_name=b"MIT", auth_data=b"abcde")
        self.assertEqual(len(request), 24)
        self.assertEqual(request[12:16], b"MIT\0")
        self.assertEqual(request[16:24], b"abcde\0\0\0")

    def test_query_extension_length_and_padding(self) -> None:
        request = query_extension("RENDER")
        self.assertEqual(len(request), 16)
        self.assertEqual(request[:8], struct.pack("<BBHHH", 98, 0, 4, 6, 0))
        self.assertEqual(request[8:], b"RENDER\0\0")


if __name__ == "__main__":
    unittest.main()
