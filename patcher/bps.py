"""BPS patches (the format byuu designed for ROM hacks; https://www.romhacking.net/documents/746/).

A patch holds only what's different: where the target matches the source byte for byte it
says "copy from the source here", and only bytes that differ are stored. So a patch made from
our co-op disc and the retail disc holds our code and the hook bytes, never game data (D71).

    create(source, target) -> patch bytes      (aligned images: no data moves, so it compares
                                                 byte for byte, in 64 KB blocks, then bytes)
    apply(source, patch) -> target bytes        (checks the source's and the target's CRC32)
"""

import zlib

SOURCE_READ, TARGET_READ, SOURCE_COPY, TARGET_COPY = 0, 1, 2, 3
BLOCK = 1 << 16


class PatchError(Exception):
    pass


def _number(n):
    out = bytearray()
    while True:
        x = n & 0x7F
        n >>= 7
        if n == 0:
            out.append(0x80 | x)
            return bytes(out)
        out.append(x)
        n -= 1


def _read_number(data, pos):
    n, shift = 0, 1
    while True:
        x = data[pos]
        pos += 1
        n += (x & 0x7F) * shift
        if x & 0x80:
            return n, pos
        shift <<= 7
        n += shift


def _diff_runs(source, target):
    """(same, start, end) runs over the target, comparing it with the source at the same offset."""
    n = len(target)
    common = min(len(source), n)
    runs = []
    pos = 0
    while pos < common:  # whole blocks that match are one comparison each
        end = min(pos + BLOCK, common)
        if source[pos:end] == target[pos:end]:
            runs.append((True, pos, end))
        else:
            i = pos
            while i < end:
                same = source[i] == target[i]
                j = i + 1
                while j < end and (source[j] == target[j]) == same:
                    j += 1
                runs.append((same, i, j))
                i = j
        pos = end
    if common < n:
        runs.append((False, common, n))
    merged = []
    for same, a, b in runs:  # join neighbours; short matches inside changes aren't worth an action
        if merged and merged[-1][0] == same and merged[-1][2] == a:
            merged[-1] = (same, merged[-1][1], b)
        else:
            merged.append((same, a, b))
    return merged


def create(source, target, metadata=b""):
    source, target = memoryview(source), memoryview(target)
    out = bytearray(b"BPS1")
    out += _number(len(source)) + _number(len(target)) + _number(len(metadata)) + metadata
    for same, a, b in _diff_runs(source, target):
        length = b - a
        if same:
            out += _number(((length - 1) << 2) | SOURCE_READ)
        else:
            out += _number(((length - 1) << 2) | TARGET_READ)
            out += target[a:b]
    out += zlib.crc32(source).to_bytes(4, "little")
    out += zlib.crc32(target).to_bytes(4, "little")
    out += zlib.crc32(out).to_bytes(4, "little")
    return bytes(out)


def info(patch):
    """(source size, target size, metadata, source CRC32, target CRC32)."""
    if patch[:4] != b"BPS1":
        raise PatchError("not a BPS patch")
    src, pos = _read_number(patch, 4)
    dst, pos = _read_number(patch, pos)
    meta_len, pos = _read_number(patch, pos)
    meta = bytes(patch[pos:pos + meta_len])
    crc_src = int.from_bytes(patch[-12:-8], "little")
    crc_dst = int.from_bytes(patch[-8:-4], "little")
    return src, dst, meta, crc_src, crc_dst


def apply(source, patch, check_source=True):
    patch = memoryview(patch)
    if zlib.crc32(patch[:-4]) != int.from_bytes(patch[-4:], "little"):
        raise PatchError("the patch file is damaged")
    src_size, dst_size, meta, crc_src, crc_dst = info(patch)
    if len(source) != src_size or (check_source and zlib.crc32(source) != crc_src):
        raise PatchError("this isn't the disc the patch was made for")
    _, pos = _read_number(patch, 4)
    _, pos = _read_number(patch, pos)
    meta_len, pos = _read_number(patch, pos)
    pos += meta_len
    end = len(patch) - 12
    out = bytearray(dst_size)
    o = src_rel = dst_rel = 0
    source = memoryview(source)
    while pos < end:
        word, pos = _read_number(patch, pos)
        action, length = word & 3, (word >> 2) + 1
        if action == SOURCE_READ:
            out[o:o + length] = source[o:o + length]
        elif action == TARGET_READ:
            out[o:o + length] = patch[pos:pos + length]
            pos += length
        else:
            delta, pos = _read_number(patch, pos)
            delta = -(delta >> 1) if delta & 1 else delta >> 1
            if action == SOURCE_COPY:
                src_rel += delta
                out[o:o + length] = source[src_rel:src_rel + length]
                src_rel += length
            else:
                dst_rel += delta
                for k in range(length):  # may overlap itself
                    out[o + k] = out[dst_rel + k]
                dst_rel += length
        o += length
    if zlib.crc32(out) != crc_dst:
        raise PatchError("the patched disc came out wrong (the patch or the disc is damaged)")
    return bytes(out)


def apply_file(source_path, patch, out_path, progress=None):
    """apply(), streaming: the source is read through mmap and the target written as it goes,
    so a 500 MB disc doesn't need 1 GB of memory. Patches we make use only SOURCE_READ and
    TARGET_READ; the copy actions aren't supported here. progress(done, total) is called now
    and then."""
    import mmap
    patch = memoryview(patch)
    if zlib.crc32(patch[:-4]) != int.from_bytes(patch[-4:], "little"):
        raise PatchError("the patch file is damaged")
    src_size, dst_size, meta, crc_src, crc_dst = info(patch)
    _, pos = _read_number(patch, 4)
    _, pos = _read_number(patch, pos)
    meta_len, pos = _read_number(patch, pos)
    pos += meta_len
    end = len(patch) - 12
    with open(source_path, "rb") as f:
        if f.seek(0, 2) != src_size:
            raise PatchError("this isn't the disc the patch was made for (wrong size)")
        source = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            crc = 0
            for k in range(0, src_size, 1 << 22):
                crc = zlib.crc32(source[k:k + (1 << 22)], crc)
                if progress:
                    progress(k, src_size * 2)
            if crc != crc_src:
                raise PatchError("this isn't the disc the patch was made for")
            crc, o = 0, 0
            with open(out_path, "wb") as out:
                while pos < end:
                    word, pos = _read_number(patch, pos)
                    action, length = word & 3, (word >> 2) + 1
                    if action == SOURCE_READ:
                        for k in range(o, o + length, 1 << 22):
                            chunk = source[k:min(k + (1 << 22), o + length)]
                            out.write(chunk)
                            crc = zlib.crc32(chunk, crc)
                    elif action == TARGET_READ:
                        chunk = patch[pos:pos + length]
                        out.write(chunk)
                        crc = zlib.crc32(chunk, crc)
                        pos += length
                    else:
                        raise PatchError("unsupported patch action")
                    o += length
                    if progress:
                        progress(src_size + o * src_size // max(dst_size, 1), src_size * 2)
        finally:
            source.close()
    if o != dst_size or crc != crc_dst:
        raise PatchError("the patched disc came out wrong (the patch or the disc is damaged)")
