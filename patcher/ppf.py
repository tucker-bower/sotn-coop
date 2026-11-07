"""PPF patches (versions 1, 2 and 3), the format SOTN mods ship in: the randomizer, SOTN Editor.

    python patcher/ppf.py image.bin patch.ppf out.bin

Applies the patch to a copy of a raw (2352-byte sector) disc image, then recomputes the
checksums of every sector it touched: the randomizer's patches leave that to the player, and
co-op's layering (layer.py) needs every sector sealed anyway.
"""

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sectors  # noqa: E402

BLOCK_CHECK_AT = 0x9320  # PPF2/3: the 1024 bytes of the image a patch was made from, at this offset
DIZ = b"@BEGIN_FILE_ID.DIZ"


class PpfError(Exception):
    pass


def records(patch):
    """(version, description, block_check or None, [(offset, bytes)])."""
    magic = patch[:5]
    if magic not in (b"PPF10", b"PPF20", b"PPF30"):
        raise PpfError("not a PPF patch")
    version = magic[3] - ord("0")
    description = patch[6:56].decode("latin-1").strip()
    end = patch.find(DIZ)
    end = len(patch) if end < 0 else end
    block = None
    if version == 1:
        at, wide, undo = 56, False, False
    elif version == 2:
        at, wide, undo, block = 1084, False, False, patch[60:1084]
    else:
        image_type, has_block, undo = patch[56], patch[57], bool(patch[58])
        if image_type != 0:
            raise PpfError("a PPF3 patch for a GI image, not a BIN")
        at, wide = (1084, True) if has_block else (60, True)
        block = patch[60:1084] if has_block else None
    out = []
    while at < end:
        if wide:
            offset, = struct.unpack_from("<Q", patch, at)
            at += 8
        else:
            offset, = struct.unpack_from("<I", patch, at)
            at += 4
        n = patch[at]
        out.append((offset, patch[at + 1:at + 1 + n]))
        at += 1 + n + (n if undo else 0)
    return version, description, block, out


def apply(image, patch):
    """A patched copy of image (bytes), with every touched sector's checksums recomputed."""
    _, _, block, recs = records(patch)
    if block is not None and image[BLOCK_CHECK_AT:BLOCK_CHECK_AT + 1024] != block:
        raise PpfError("this patch was made for a different disc image")
    out = bytearray(image)
    touched = set()
    for offset, data in recs:
        if offset + len(data) > len(out):
            out.extend(bytes(offset + len(data) - len(out)))
        out[offset:offset + len(data)] = data
        touched.update(range(offset // sectors.SECTOR, (offset + len(data) - 1) // sectors.SECTOR + 1))
    for i in touched:
        s = out[i * sectors.SECTOR:(i + 1) * sectors.SECTOR]
        if len(s) == sectors.SECTOR and sectors.is_data(s):
            sectors.seal(s)
            out[i * sectors.SECTOR:(i + 1) * sectors.SECTOR] = s
    return out


def main():
    image, patch, out = sys.argv[1:4]
    version, description, _, recs = records(Path(patch).read_bytes())
    print(f"PPF{version}: {description!r}, {len(recs)} records")
    Path(out).write_bytes(apply(Path(image).read_bytes(), Path(patch).read_bytes()))


if __name__ == "__main__":
    main()
