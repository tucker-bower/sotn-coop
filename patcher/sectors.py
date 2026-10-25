"""CD-ROM sector checksums (MODE2/2352), so a patch never carries them (D71).

A raw form 1 sector ends in an EDC (a CRC) and ECC (Reed-Solomon parity) computed from its data
(form 2's EDC is optional, and this disc leaves it at 0). For a sector we changed, those bytes
are a function of the game's bytes around our change: the patch stores them as zeros (neutral),
and the patcher computes them on the player's PC.

    neutral(sector) -> sector with its EDC/ECC zeroed
    seal(sector)    -> sector with its EDC/ECC computed (in place, bytearray)

Ported from upstream's tools/sotn-disk/iso9660/ecc.go (ECMA-130).
"""

SECTOR = 2352
FORM2 = 0x20  # subheader submode bit


def _tables():
    f_lut, b_lut, edc_lut = bytearray(256), bytearray(256), [0] * 256
    for i in range(256):
        j = (i << 1) ^ (0x11D if i & 0x80 else 0)
        f_lut[i] = j & 0xFF
        b_lut[i ^ (j & 0xFF)] = i
        edc = i
        for _ in range(8):
            edc = (edc >> 1) ^ 0xD8018001 if edc & 1 else edc >> 1
        edc_lut[i] = edc
    return bytes(f_lut), bytes(b_lut), edc_lut


F_LUT, B_LUT, EDC_LUT = _tables()


def edc(data):
    e = 0
    for b in data:
        e = (e >> 8) ^ EDC_LUT[(e ^ b) & 0xFF]
    return e


def _ecc_block(src, major_count, minor_count, major_mult, minor_inc, dest, at):
    size = major_count * minor_count
    for major in range(major_count):
        index = (major >> 1) * major_mult + (major & 1)
        a = b = 0
        for _ in range(minor_count):
            v = src[index]
            a = F_LUT[a ^ v]
            b ^= v
            index += minor_inc
            if index >= size:
                index -= size
        a = B_LUT[F_LUT[a] ^ b]
        dest[at + major] = a
        dest[at + major + major_count] = a ^ b


def is_data(sector):
    """A MODE2 data sector (sync pattern and mode 2), not CD audio."""
    return sector[0:12] == b"\x00" + b"\xff" * 10 + b"\x00" and sector[15] == 2


def neutral(sector):
    s = bytearray(sector)
    if is_data(s) and not s[18] & FORM2:  # form 2's EDC is optional: the disc leaves it at 0
        s[0x818:SECTOR] = bytes(SECTOR - 0x818)
    return bytes(s)


def seal(s):
    """Computes the EDC/ECC of a MODE2 sector in place (a bytearray)."""
    if not is_data(s) or s[18] & FORM2:
        return s
    s[0x818:0x81C] = edc(s[0x10:0x818]).to_bytes(4, "little")
    header = s[12:16]
    s[12:16] = bytes(4)  # form 1 ECC is computed with the address zeroed
    body = memoryview(s)[12:]
    _ecc_block(body, 86, 24, 2, 86, s, 0x81C)
    _ecc_block(body, 52, 43, 86, 88, s, 0x8C8)
    s[12:16] = header
    return s
