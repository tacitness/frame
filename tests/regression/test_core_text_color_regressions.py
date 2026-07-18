from __future__ import annotations

import struct
import unittest
from pathlib import Path

from tests.lib.server import FrameServer
from tests.lib.x11 import (
    create_gc,
    create_window,
    get_image,
    get_window_attributes,
    image_text8,
    map_subwindows,
    map_window,
    poly_text8,
    query_colors,
    receive_reply,
)


WINDOW_BACKGROUND = 0x00010203
TEXT_FOREGROUND = 0x00EEDDCC
TEXT_BACKGROUND = 0x00112233

# Public-domain X.Org font-misc-misc 6x13 glyph A, BBX 6x13+0-2.
GLYPH_A = (
    0x00,
    0x00,
    0x20,
    0x50,
    0x88,
    0x88,
    0x88,
    0xF8,
    0x88,
    0x88,
    0x88,
    0x00,
    0x00,
)


class CoreTextColorRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.server = FrameServer(Path("frame")).start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop()

    def test_query_colors_returns_exact_truecolor_rgb_records(self) -> None:
        connection, _setup = self.server.connect()
        self.addCleanup(connection.close)
        pixels = (0x00000000, 0x00112233, 0x00FFFFFF)
        connection.sendall(query_colors(pixels))

        header, body = receive_reply(connection)

        self.assertEqual(struct.unpack_from("<H", header, 2)[0], 1)
        self.assertEqual(struct.unpack_from("<I", header, 4)[0], 2 * len(pixels))
        self.assertEqual(struct.unpack_from("<H", header, 8)[0], len(pixels))
        self.assertEqual(
            [struct.unpack_from("<HHH", body, offset) for offset in range(0, 24, 8)],
            [(0x0000, 0x0000, 0x0000), (0x1111, 0x2222, 0x3333), (0xFFFF,) * 3],
        )
        self.assertEqual(body[6::8], b"\0\0\0")
        self.assertEqual(body[7::8], b"\0\0\0")

    def test_query_colors_streams_a_reply_larger_than_reply_buffer(self) -> None:
        connection, _setup = self.server.connect()
        self.addCleanup(connection.close)
        pixels = tuple((index & 0xFF) * 0x010101 for index in range(2050))
        connection.sendall(query_colors(pixels))

        header, body = receive_reply(connection)

        self.assertEqual(struct.unpack_from("<I", header, 4)[0], 2 * len(pixels))
        self.assertEqual(struct.unpack_from("<H", header, 8)[0], len(pixels))
        self.assertEqual(len(body), len(pixels) * 8)
        for index in (0, 1, 2048, 2049):
            channel = (pixels[index] >> 16) & 0xFF
            self.assertEqual(
                struct.unpack_from("<HHH", body, index * 8),
                (channel * 0x101,) * 3,
            )

    def test_image_text8_renders_xorg_fixed_6x13_image_semantics(self) -> None:
        connection, setup = self.server.connect()
        self.addCleanup(connection.close)
        window = setup.resource_id_base | 1
        gc = setup.resource_id_base | 2
        requests = (
            create_window(
                window,
                width=12,
                height=16,
                background=WINDOW_BACKGROUND,
            )
            + create_gc(
                gc,
                window,
                foreground=TEXT_FOREGROUND,
                background=TEXT_BACKGROUND,
            )
            + image_text8(window, gc, 2, 12, b"A")
            + get_image(window, x=0, y=0, width=12, height=16)
        )
        connection.sendall(requests)

        header, body = receive_reply(connection)

        self.assertEqual(struct.unpack_from("<H", header, 2)[0], 4)
        pixels = struct.unpack(f"<{12 * 16}I", body)
        for row in range(16):
            for column in range(12):
                expected = WINDOW_BACKGROUND
                glyph_row = row - 1  # baseline 12 - ascent 11
                glyph_column = column - 2
                if 0 <= glyph_row < 13 and 0 <= glyph_column < 6:
                    expected = TEXT_BACKGROUND
                    if GLYPH_A[glyph_row] & (0x80 >> glyph_column):
                        expected = TEXT_FOREGROUND
                self.assertEqual(
                    pixels[row * 12 + column] & 0xFFFFFF,
                    expected,
                    f"unexpected pixel at ({column}, {row})",
                )

    def test_truncated_image_text8_does_not_consume_next_request(self) -> None:
        connection, _setup = self.server.connect()
        self.addCleanup(connection.close)
        malformed = struct.pack("<BBHIIhh", 76, 4, 4, 0x80, 0, 0, 12)
        connection.sendall(malformed + query_colors((0x00123456,)))

        header, body = receive_reply(connection)

        self.assertEqual(struct.unpack_from("<H", header, 2)[0], 2)
        self.assertEqual(struct.unpack_from("<HHH", body, 0), (0x1212, 0x3434, 0x5656))
        self.server.assert_running()

    def test_poly_text8_is_transparent_and_applies_element_deltas(self) -> None:
        connection, setup = self.server.connect()
        self.addCleanup(connection.close)
        window = setup.resource_id_base | 1
        gc = setup.resource_id_base | 2
        requests = (
            create_window(
                window,
                width=24,
                height=16,
                background=WINDOW_BACKGROUND,
            )
            + create_gc(
                gc,
                window,
                foreground=TEXT_FOREGROUND,
                background=TEXT_BACKGROUND,
            )
            + poly_text8(window, gc, 5, 12, ((-2, b"A"), (3, b"A")))
            + get_image(window, x=0, y=0, width=24, height=16)
        )
        connection.sendall(requests)

        _header, body = receive_reply(connection)

        pixels = struct.unpack(f"<{24 * 16}I", body)
        cell_starts = (3, 12)
        for row in range(16):
            for column in range(24):
                expected = WINDOW_BACKGROUND
                glyph_row = row - 1
                if 0 <= glyph_row < 13:
                    for cell_start in cell_starts:
                        glyph_column = column - cell_start
                        if (
                            0 <= glyph_column < 6
                            and GLYPH_A[glyph_row] & (0x80 >> glyph_column)
                        ):
                            expected = TEXT_FOREGROUND
                            break
                self.assertEqual(
                    pixels[row * 24 + column] & 0xFFFFFF,
                    expected,
                    f"unexpected transparent-text pixel at ({column}, {row})",
                )

    def test_truncated_poly_text8_does_not_consume_next_request(self) -> None:
        connection, setup = self.server.connect()
        self.addCleanup(connection.close)
        window = setup.resource_id_base | 1
        gc = setup.resource_id_base | 2
        malformed = (
            struct.pack("<BBHIIhh", 74, 0, 5, window, gc, 0, 12)
            + bytes((4, 0, ord("A"), 0))
        )
        connection.sendall(
            create_window(window, width=12, height=16, background=WINDOW_BACKGROUND)
            + create_gc(
                gc,
                window,
                foreground=TEXT_FOREGROUND,
                background=TEXT_BACKGROUND,
            )
            + malformed
            + query_colors((0x00123456,))
        )

        header, body = receive_reply(connection)

        self.assertEqual(struct.unpack_from("<H", header, 2)[0], 4)
        self.assertEqual(struct.unpack_from("<HHH", body, 0), (0x1212, 0x3434, 0x5656))
        self.server.assert_running()

    def test_map_subwindows_maps_every_direct_child_only(self) -> None:
        connection, setup = self.server.connect()
        self.addCleanup(connection.close)
        parent = setup.resource_id_base | 1
        first_child = setup.resource_id_base | 2
        second_child = setup.resource_id_base | 3
        grandchild = setup.resource_id_base | 4
        connection.sendall(
            create_window(parent)
            + create_window(first_child, parent=parent)
            + create_window(second_child, parent=parent)
            + create_window(grandchild, parent=first_child)
            + map_window(parent)
            + map_subwindows(parent)
            + get_window_attributes(first_child)
            + get_window_attributes(second_child)
            + get_window_attributes(grandchild)
        )

        first_header, _first_body = receive_reply(connection)
        second_header, _second_body = receive_reply(connection)
        grandchild_header, _grandchild_body = receive_reply(connection)

        self.assertEqual(struct.unpack_from("<H", first_header, 2)[0], 7)
        self.assertEqual(struct.unpack_from("<H", second_header, 2)[0], 8)
        self.assertEqual(struct.unpack_from("<H", grandchild_header, 2)[0], 9)
        self.assertEqual(first_header[26], 2)
        self.assertEqual(second_header[26], 2)
        self.assertEqual(grandchild_header[26], 0)


if __name__ == "__main__":
    unittest.main()
