"""A disc image as the sectors where it differs from retail: how the launcher keeps a randomized
disc (kilobytes to a few megabytes, not 540 MB), on the player's machine only.

    make(retail, other) -> bytes      apply(retail, diff) -> bytes

The format: b"SDIF", the image's length, then zlib of each changed sector's number and 2352 bytes.
"""

import struct
import zlib

SECTOR = 2352
MAGIC = b"SDIF"


class DiffError(Exception):
    pass


def make(retail, other):
    n = max(len(retail), len(other)) // SECTOR
    mv_r, mv_o = memoryview(retail), memoryview(other)
    body = bytearray()
    for i in range(n):
        a, b = mv_r[i * SECTOR:(i + 1) * SECTOR], mv_o[i * SECTOR:(i + 1) * SECTOR]
        if a != b:
            body += struct.pack("<I", i) + bytes(b).ljust(SECTOR, b"\0")
    return MAGIC + struct.pack("<Q", len(other)) + zlib.compress(bytes(body), 6)


def apply(retail, diff):
    if diff[:4] != MAGIC:
        raise DiffError("not a sector diff")
    (length,) = struct.unpack_from("<Q", diff, 4)
    try:
        body = zlib.decompress(diff[12:])
    except zlib.error as e:
        raise DiffError(f"damaged ({e})") from e
    if len(body) % (4 + SECTOR):
        raise DiffError("damaged (cut short)")
    out = bytearray(retail[:length])
    out.extend(bytes(length - len(out)))
    for at in range(0, len(body), 4 + SECTOR):
        (i,) = struct.unpack_from("<I", body, at)
        if (i + 1) * SECTOR > length:
            raise DiffError("a sector past the end of the image")
        out[i * SECTOR:(i + 1) * SECTOR] = body[at + 4:at + 4 + SECTOR]
    return bytes(out)
