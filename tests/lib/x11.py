"""Small X11 wire helpers used by unit, integration, and regression tests."""

from __future__ import annotations

import socket
import struct
from dataclasses import dataclass


@dataclass(frozen=True)
class SetupReply:
    protocol_major: int
    protocol_minor: int
    release_number: int
    resource_id_base: int
    resource_id_mask: int
    maximum_request_length: int
    roots: int
    pixmap_formats: tuple[tuple[int, int, int], ...]
    vendor: str
    raw: bytes


def pad4(length: int) -> int:
    return (length + 3) & ~3


def setup_request(
    *, byte_order: bytes = b"l", major: int = 11, minor: int = 0,
    auth_name: bytes = b"", auth_data: bytes = b""
) -> bytes:
    if len(byte_order) != 1:
        raise ValueError("byte_order must be one byte")
    endian = "<" if byte_order == b"l" else ">"
    header = byte_order + b"\0" + struct.pack(
        endian + "HHHHH", major, minor, len(auth_name), len(auth_data), 0
    )
    return (
        header
        + auth_name.ljust(pad4(len(auth_name)), b"\0")
        + auth_data.ljust(pad4(len(auth_data)), b"\0")
    )


def query_extension(name: str) -> bytes:
    encoded = name.encode("ascii")
    length = 8 + pad4(len(encoded))
    return (
        struct.pack("<BBHHH", 98, 0, length // 4, len(encoded), 0)
        + encoded.ljust(pad4(len(encoded)), b"\0")
    )


def query_colors(pixels: tuple[int, ...], *, colormap: int = 0x81) -> bytes:
    """Encode core QueryColors for frame's single TrueColor colormap."""
    return (
        struct.pack("<BBHI", 91, 0, 2 + len(pixels), colormap)
        + struct.pack(f"<{len(pixels)}I", *pixels)
    )


def create_window(
    window: int,
    *,
    parent: int = 0x80,
    visual: int = 0x20,
    x: int = 0,
    y: int = 0,
    width: int = 64,
    height: int = 64,
    background: int = 0,
) -> bytes:
    """Encode a depth-24 InputOutput window with a solid background."""
    fixed = struct.pack(
        "<BBHIIhhHHHHII",
        1,
        24,
        9,
        window,
        parent,
        x,
        y,
        width,
        height,
        0,
        1,
        visual,
        1 << 1,
    )
    return fixed + struct.pack("<I", background)


def create_gc(
    gc: int, drawable: int, *, foreground: int, background: int
) -> bytes:
    """Encode CreateGC with the two colors used by ImageText8."""
    return struct.pack(
        "<BBHIIIII",
        55,
        0,
        6,
        gc,
        drawable,
        (1 << 2) | (1 << 3),
        foreground,
        background,
    )


def map_window(window: int) -> bytes:
    """Encode core MapWindow."""
    return struct.pack("<BBHI", 8, 0, 2, window)


def map_subwindows(parent: int) -> bytes:
    """Encode core MapSubwindows."""
    return struct.pack("<BBHI", 9, 0, 2, parent)


def get_window_attributes(window: int) -> bytes:
    """Encode core GetWindowAttributes."""
    return struct.pack("<BBHI", 3, 0, 2, window)


def image_text8(drawable: int, gc: int, x: int, y: int, text: bytes) -> bytes:
    """Encode fixed-font core ImageText8, including protocol padding."""
    if len(text) > 255:
        raise ValueError("ImageText8 accepts at most 255 bytes")
    padded = text.ljust(pad4(len(text)), b"\0")
    return (
        struct.pack(
            "<BBHIIhh", 76, len(text), (16 + len(padded)) // 4, drawable, gc, x, y
        )
        + padded
    )


def poly_text8(
    drawable: int,
    gc: int,
    x: int,
    y: int,
    elements: tuple[tuple[int, bytes], ...],
) -> bytes:
    """Encode core PolyText8 STRING8 elements with signed element deltas."""
    body = bytearray()
    for delta, text in elements:
        if not -128 <= delta <= 127:
            raise ValueError("PolyText8 delta must fit INT8")
        if len(text) > 254:
            raise ValueError("PolyText8 text elements accept at most 254 bytes")
        body.extend(struct.pack("<Bb", len(text), delta))
        body.extend(text)
    padded = bytes(body).ljust(pad4(len(body)), b"\0")
    return (
        struct.pack(
            "<BBHIIhh", 74, 0, (16 + len(padded)) // 4, drawable, gc, x, y
        )
        + padded
    )


def get_image(
    drawable: int, *, x: int, y: int, width: int, height: int
) -> bytes:
    """Encode a depth-24 ZPixmap GetImage request."""
    return struct.pack(
        "<BBHIhhHHI", 73, 2, 5, drawable, x, y, width, height, 0xFFFFFFFF
    )


def recv_exact(connection: socket.socket, length: int) -> bytes:
    chunks: list[bytes] = []
    remaining = length
    while remaining:
        chunk = connection.recv(remaining)
        if not chunk:
            raise EOFError(f"connection closed with {remaining} bytes outstanding")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def receive_reply(connection: socket.socket) -> tuple[bytes, bytes]:
    """Receive a core 32-byte reply header and its declared body."""
    header = recv_exact(connection, 32)
    if header[0] != 1:
        raise AssertionError(f"expected X11 reply, got response type {header[0]}")
    body = recv_exact(connection, struct.unpack_from("<I", header, 4)[0] * 4)
    return header, body


def receive_setup(connection: socket.socket) -> SetupReply:
    header = recv_exact(connection, 8)
    status, _unused, major, minor, body_words = struct.unpack("<BBHHH", header)
    if status != 1:
        raise AssertionError(f"X11 setup failed with status {status}")
    body = recv_exact(connection, body_words * 4)
    if len(body) < 32:
        raise AssertionError("X11 setup body is shorter than the fixed header")
    release, rid_base, rid_mask, _motion = struct.unpack_from("<IIII", body, 0)
    vendor_length, max_request = struct.unpack_from("<HH", body, 16)
    roots, format_count = struct.unpack_from("<BB", body, 20)
    vendor_start = 32
    vendor_end = vendor_start + vendor_length
    vendor = body[vendor_start:vendor_end].decode("ascii")
    format_start = vendor_start + pad4(vendor_length)
    formats = tuple(
        struct.unpack_from("<BBB", body, format_start + index * 8)
        for index in range(format_count)
    )
    return SetupReply(
        protocol_major=major,
        protocol_minor=minor,
        release_number=release,
        resource_id_base=rid_base,
        resource_id_mask=rid_mask,
        maximum_request_length=max_request,
        roots=roots,
        pixmap_formats=formats,
        vendor=vendor,
        raw=header + body,
    )
