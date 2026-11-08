"""Saturn Maria's art, from the player's own Saturn disc (docs/design/character-mods.md, D181).

    arrays(read_saturn, read_ps1) -> {C symbol: bytes}

SOTN Ultimate's Saturn Maria (characters/maria-saturn) compiles her images, frame tables,
palettes, animations and effects into her overlay as C arrays that SOTN Ultimate generates from
the Saturn disc. They are game data, so her shipped overlay has them blank, and this fills them
on the player's machine. A line-by-line port of SOTN Ultimate's browser builder
(mods/sotn-ultimate/tools/builder/src/mar_assets.ts at df11991, by renanbianchi, AGPL-3.0;
itself a byte-exact port of its gen_mar_assets.py). Pure Python, for the Windows build and
Android alike. read_saturn(name) gives a Saturn disc file by name (MARIA.PRG, MARIA.CHR,
MAR_W.CHR, 0.BIN, STAGE_01.CHR); read_ps1(path) a PS1 one (BIN/RIC.BIN).
"""

SAT = 0x060A5000
PHASE = 4
IMAGE_TABLE, PALETTE_TABLE = 0x060C51A8, 0x060C398C
ANIMATION_START, ANIMATION_END, FRAME_TABLE = 0x060C28D8, 0x060C37CC, 0x060C4BB0
HITBOX_TABLE = 0x060C37CC
STAND = 0x060C28E8

# pl_anims.c's tables in order: (name, Saturn Maria animation), (name, RIC.BIN offset, pairs:
# Richter's timing, her standing pose) or (name,): the hitbox table
PL_ANIMS = [
    ("ric_anim_press_up", 103316, 2), ("ric_anim_stop_run", 103324, 8),
    ("ric_anim_stand", 0x060C28E8), ("ric_anim_stand_relax", 0x060C28E8), ("ric_anim_walk", 0x060C29B0),
    ("ric_anim_crouch_from_stand2", 0x060C2AA8), ("ric_anim_crouch", 0x060C2AB0),
    ("ric_anim_land_from_air_run", 103624, 2), ("ric_anim_crouch_from_stand", 103632, 4),
    ("D_801554E0", 0x060C2BEC), ("D_801554F0", 0x060C2B18), ("D_8015550C", 0x060C2ADC),
    ("D_80155528", 0x060C2B38), ("D_80155534", 0x060C2B38), ("D_80155544", 0x060C2DB8),
    ("D_8015555C", 0x060C3704), ("D_80155588", 0x060C3760), ("D_801555A8", 0x060C30B0),
    ("D_801555C8", 0x060C30EC), ("D_801555E8", 0x060C2ED8), ("ric_anim_throw_daggers", 103944, 12),
    ("D_80155638", 0x060C2F00), ("ric_anim_stand_in_air", 104024, 6), ("ric_anim_run", 0x060C2A18),
    ("ric_anim_stun", 0x060C2C28), ("D_8015569C", 0x060C2D84), ("D_801556C4", 0x060C2C28),
    ("D_80155704", 0x060C2D84), ("ric_anim_brandish_whip", 0x060C28D8), ("D_80155738", 104248, 2),
    ("D_80155740", 0x060C2B38), ("D_80155748", 104264, 2), ("D_80155750", 0x060C2E4C),
    ("D_8015577C", 0x060C2F8C), ("D_80155788", 0x060C3720), ("ric_anim_high_jump", 0x060C2BB8),
    ("ric_anim_point_finger_up", 104364, 11), ("ric_anim_blade_dash", 0x060C2ADC),
    ("ric_anim_flame_whip", 104512, 29), ("D_801558B4", 104628, 8), ("D_801558D4", 104660, 2),
    ("D_801558DC", 104668, 2), ("D_801558E4", 104676, 14), ("D_8015591C", 0x060C3788),
    ("D_80155950", 0x060C37B8), ("D_80155964",),
]
# ANIM_MAP in its (dict) order, for the names of her POSE_JUMP group
ANIM_MAP_ORDER = [
    ("ric_anim_stand", 0x060C28E8), ("ric_anim_stand_relax", 0x060C28E8), ("ric_anim_walk", 0x060C29B0),
    ("ric_anim_crouch_from_stand2", 0x060C2AA8), ("ric_anim_crouch", 0x060C2AB0), ("D_801554E0", 0x060C2BEC),
    ("D_80155544", 0x060C2DB8), ("D_8015555C", 0x060C3704), ("D_80155588", 0x060C3760),
    ("D_801555A8", 0x060C30B0), ("D_801555C8", 0x060C30EC), ("D_801555E8", 0x060C2ED8),
    ("D_80155638", 0x060C2F00), ("ric_anim_run", 0x060C2A18), ("ric_anim_stun", 0x060C2C28),
    ("D_8015569C", 0x060C2D84), ("D_801556C4", 0x060C2C28), ("D_80155704", 0x060C2D84),
    ("ric_anim_brandish_whip", 0x060C28D8), ("D_80155740", 0x060C2B38), ("D_80155788", 0x060C3720),
    ("ric_anim_high_jump", 0x060C2BB8), ("ric_anim_blade_dash", 0x060C2ADC), ("D_801554F0", 0x060C2B18),
    ("D_8015550C", 0x060C2ADC), ("D_80155528", 0x060C2B38), ("D_80155534", 0x060C2B38),
    ("D_80155750", 0x060C2E4C), ("D_8015577C", 0x060C2F8C), ("D_8015591C", 0x060C3788),
    ("D_80155950", 0x060C37B8),
]
EXTRA_ANIMS = [
    ("mar_anim_atk_air_down", 0x060C3114), ("mar_anim_kick", 0x060C2FA4),
    ("mar_anim_kick_crouch", 0x060C3080), ("mar_anim_kick_air_fall", 0x060C2F18),
    ("mar_anim_kick_air_rise", 0x060C3734), ("mar_anim_atk_end", 0x060C3164),
    ("mar_anim_atk_end_b", 0x060C3184), ("mar_anim_kick_end", 0x060C2FC8),
    ("mar_anim_kick_end_b", 0x060C2FF0), ("mar_anim_kick_crouch_end", 0x060C309C),
    ("mar_anim_dive", 0x060C2F48), ("mar_anim_dive_down", 0x060C2F54),
    ("mar_anim_uppercut_diag", 0x060C2B04), ("mar_anim_roll", 0x060C2E64),
    ("mar_anim_stand_edge", 0x060C292C), ("mar_anim_backdash", 0x060C2E04),
    ("mar_anim_backdash_end", 0x060C2E34), ("mar_anim_backdash_end_b", 0x060C2E40),
    ("mar_anim_throw", 0x060C2E78), ("mar_anim_throw_b", 0x060C2EA8),
    ("mar_anim_sp_knuckle", 0x060C3518), ("mar_anim_sp_genbu", 0x060C31AC),
    ("mar_anim_sp_genbu2", 0x060C31E8), ("mar_anim_sp_byakko", 0x060C33D8),
    ("mar_anim_sp_byakko2", 0x060C3438), ("mar_anim_sp_byakko3", 0x060C34D4),
    ("mar_anim_sp_byakko4", 0x060C34F8), ("mar_anim_sp_seiryu", 0x060C32BC),
    ("mar_anim_sp_seiryu2", 0x060C32F8), ("mar_anim_sp_seiryu3", 0x060C3390),
    ("mar_anim_sp_seiryu4", 0x060C33B0), ("mar_anim_sp_summon", 0x060C3258),
    ("mar_anim_sp_summon2", 0x060C3284),
]
ANIM_GROUPS = 0x060C28A0

FX_RES = 0x060C6D68
FX_ORDER = [1, 2, 3, 8, 4, 6, 5, 7, 9, 10, 11, 12]
FX_NFRAMES = {1: 55, 2: 2, 3: 4, 4: 13, 5: 38, 6: 5, 7: 9, 8: 17, 9: 20, 10: 10, 11: 14, 12: 19}
FX_VRAM_X, FX_VRAM_Y, FX_VRAM_W = 992, 384, 32
SP_PERM_VRAM = (960, 384)
SP_SLOT_VRAM = (800, 384)
SP_SLOT_ROWS = 504 - 384
SP_FLAME_VRAM = (992, 458)
SP_PUFF_VRAM = (896, 385)


def tileset(x, y):
    return ((x // 64) + (y // 256) * 16) << 2


FX_TILESET = tileset(FX_VRAM_X, FX_VRAM_Y)
U_FIRST = 1
FX_BANKS = [("mar_fxbank_shot", 7, list(range(1, 9))), ("mar_fxbank_ball", 1, list(range(1, 13)) + [16])]
FX_PALS = [(7, 0, 0x140), (1, 0, 0x139), (1, 1, 0x13A), (1, 3, 0x13B)]
# the mod's own colours (her holy water flames, recoloured)
FLAME_PAL = (0x13F, [0x0000, 0xD84C, 0xC84C, 0xD84C, 0xE44C, 0xF04C, 0xE84C, 0xD84C,
                     0xCC4C, 0xC84C, 0xD04C, 0xD84C, 0xDC4C, 0xE44C, 0xE84C, 0xF44C])
CHARGE_PALS = 0x060C16D0
SP_PERM = [
    ("mar_fxbank_perm", 11, list(range(1, 14)), (0, 0), [0x141]),
    ("mar_fxbank_perm", 12, list(range(13, 19)), (1, 1), [0x142]),
    ("mar_fxbank_perm", "S4", list(range(1, 11)), (19, 4), [0x145]),
]
SP_PUFF = ("mar_fxbank_perm", "S9", list(range(1, 15)), (29, 5), [0x146])
SP_GROUPS = [
    ("mar_fxbank_knuckle", 8, list(range(1, 16))),
    ("mar_fxbank_genbu", 9, list(range(1, 19))),
    ("mar_fxbank_byakko", 10, list(range(1, 9))),
    ("mar_fxbank_seiryu", 12, [10, 11]),
]
SP_TRANSPOSE = {"12,3"}
SP_CHUNK = 4816
# 0.BIN (loaded at 0x06004080): the shared sprite banks' resources, and the frame counts of the
# banks whose frame tables (right before the images) are used
ZERO = 0x06004080
SHARED_RES = [0x060457F0, 0x06045FA0, 0x0604604C, 0x0604622C, 0x060464C4, 0x060466E0, 0x0604672C,
              0x06046BF8, 0x06046D08, 0x06046E5C, 0x06047414, 0x06047518, 0x06047570, 0x06047614, 0x06047694]
SHARED_FRAMES = {9: 15, 11: 8}


def be16(d, o):
    return (d[o] << 8) | d[o + 1]


def bes16(d, o):
    v = be16(d, o)
    return v - 0x10000 if v & 0x8000 else v


def be32(d, o):
    return (d[o] << 24) | (d[o + 1] << 16) | (d[o + 2] << 8) | d[o + 3]


def s8(d, o):
    return d[o] - 256 if d[o] & 0x80 else d[o]


def r08(v):
    return round(v * 0.8)  # Python's round is half-to-even, as the builder's roundHalfEven


class Img:
    """An h x w image of 4bpp indices, row major."""
    __slots__ = ("w", "h", "px")

    def __init__(self, h, w, px=None):
        self.w, self.h = w, h
        self.px = px if px is not None else bytearray(w * h)

    def row(self, y):
        return self.px[y * self.w:(y + 1) * self.w]


def sub(im, y0, y1, x0, x1):
    o = Img(y1 - y0, x1 - x0)
    for y in range(o.h):
        o.px[y * o.w:(y + 1) * o.w] = im.px[(y0 + y) * im.w + x0:(y0 + y) * im.w + x1]
    return o


def cols(im, keep):
    o = Img(im.h, len(keep))
    for y in range(im.h):
        r = im.px[y * im.w:(y + 1) * im.w]
        o.px[y * o.w:(y + 1) * o.w] = bytes(r[k] for k in keep)
    return o


def transpose(im):
    o = Img(im.w, im.h)
    for y in range(im.h):
        for x in range(im.w):
            o.px[x * o.w + y] = im.px[y * im.w + x]
    return o


def blit(dst, im, top, left, opaque_only=False):
    if top < 0 or left < 0 or top + im.h > dst.h or left + im.w > dst.w:
        raise ValueError("blit outside the atlas")
    for y in range(im.h):
        r = im.px[y * im.w:(y + 1) * im.w]
        o = (top + y) * dst.w + left
        if not opaque_only:
            dst.px[o:o + im.w] = r
        else:
            for x, v in enumerate(r):
                if v:
                    dst.px[o + x] = v


def nibbles(d, w, h):
    """4bpp nibbles, high first (the Saturn's)."""
    n = (w * h) >> 1
    if len(d) < n:
        raise ValueError("short image data")
    im = Img(h, w)
    px = im.px
    for i in range(n):
        b = d[i]
        px[2 * i] = b >> 4
        px[2 * i + 1] = b & 15
    return im


def pack_psx(im):
    """Low nibble first (the PS1's)."""
    n = len(im.px)
    if n & 1:
        raise ValueError("odd pixel count")
    p = im.px
    return bytes(p[2 * i] | (p[2 * i + 1] << 4) for i in range(n >> 1))


def narrow(im, left, phase):
    """Drop the columns whose absolute x (left + c) % 5 == phase; a dropped pixel with no
    neighbour in its row keeps its place."""
    keep = [c for c in range(im.w) if (left + c) % 5 != phase]
    out = cols(im, keep)
    for c in range(im.w):
        if (left + c) % 5 != phase:
            continue
        dst = -1
        for y in range(im.h):
            v = im.px[y * im.w + c]
            nl = im.px[y * im.w + c - 1] if c > 0 else 0
            nr = im.px[y * im.w + c + 1] if c + 1 < im.w else 0
            if v != 0 and nl == 0 and nr == 0:
                if dst < 0:
                    d = sum(1 for cc in range(c) if (left + cc) % 5 != phase)
                    dst = min(max(d - 1, 0), out.w - 1)
                    if dst < 0:
                        raise ValueError("narrow: no column left")
                out.px[y * out.w + dst] = v
    return out


def crop(im):
    """(image cropped to its pixels, width padded to 4, x0, y0)."""
    y0 = x0 = 1 << 30
    y1 = x1 = -1
    for y in range(im.h):
        r = im.px[y * im.w:(y + 1) * im.w]
        if not any(r):
            continue
        y0, y1 = min(y0, y), max(y1, y)
        first = next(i for i, v in enumerate(r) if v)
        last = im.w - 1 - next(i for i, v in enumerate(reversed(r)) if v)
        x0, x1 = min(x0, first), max(x1, last)
    if y1 < 0:
        return Img(min(1, im.h), min(4, im.w)), 0, 0
    c = sub(im, y0, y1 + 1, x0, x1 + 1)
    w = (c.w + 3) & ~3
    if w == c.w:
        return c, x0, y0
    p = Img(c.h, w)
    blit(p, c, 0, 0)
    return p, x0, y0


def mapcol(c):
    """PS1 column of a kept absolute Saturn column (PHASE 4)."""
    return c - (c + 1) // 5


def kept_cols(left, w):
    return [x for x in range(left, left + w) if x % 5 != PHASE]


def ps1_color(c, i):
    return 0 if i == 0 else ((c & 0x7FFF) or 0x8000)


def decompress_lzss(data):
    """One exact-count Saturn LZSS stream (no end marker)."""
    dic = bytearray(0x400)
    cursor = 0x3DE
    out = bytearray()
    src = flags = 0
    n = len(data)
    while src < n:
        flags >>= 1
        if not flags & 0x100:
            flags = data[src] | 0xFF00
            src += 1
        if flags & 1:
            if src >= n:
                break
            v = data[src]
            src += 1
            out.append(v)
            dic[cursor] = v
            cursor = (cursor + 1) & 0x3FF
        else:
            if src + 1 >= n:
                break
            first, second = data[src], data[src + 1]
            src += 2
            index = first | ((second & 0xE0) << 3)
            for i in range((second & 0x1F) + 3):
                v = dic[(index + i) & 0x3FF]
                out.append(v)
                dic[cursor] = v
                cursor = (cursor + 1) & 0x3FF
    return bytes(out)


def mb_lzss(data):
    """The PS1 overlay's LZSS (cen_maria.ts mbLzss): 8 flags a byte, a set bit a literal; a
    match is 12 bits back and 4 bits of length - 3."""
    out = bytearray()
    n = len(data)
    heads = {}
    i = 0
    while i < n:
        flag_pos = len(out)
        out.append(0)
        flags = 0
        for bit in range(8):
            if i >= n:
                break
            best_len = best_off = 0
            if i + 2 < n:
                chain = heads.get((data[i] << 16) | (data[i + 1] << 8) | data[i + 2], ())
                for c in range(len(chain) - 1, -1, -1):
                    j = chain[c]
                    if i - j > 4096:
                        break
                    k = 0
                    while k < 18 and i + k < n and data[j + k] == data[i + k]:
                        k += 1
                    if k > best_len:
                        best_len, best_off = k, i - j
                        if k == 18:
                            break
            if best_len >= 3:
                v = (best_off - 1) | ((best_len - 3) << 12)
                out += bytes((v & 0xFF, v >> 8))
                step = best_len
            else:
                flags |= 1 << bit
                out.append(data[i])
                step = 1
            for k in range(step):
                if i + k + 2 < n:
                    heads.setdefault((data[i + k] << 16) | (data[i + k + 1] << 8) | data[i + k + 2], []).append(i + k)
            i += step
        out[flag_pos] = flags
    return bytes(out)


class MariaSaturn:
    """MARIA.PRG / MARIA.CHR: her images, frames and palettes."""

    def __init__(self, prg, chr_):
        self.prg, self.chr = prg, chr_
        self.recs, self.streams, self.cache = [], [], {}
        cur, prev = IMAGE_TABLE - SAT, -1
        while cur + 4 <= len(prg):
            dims, units = be16(prg, cur), be16(prg, cur + 2)
            w, h = dims >> 8, dims & 0xFF
            if not w or not h or w > 128 or h > 128 or units < prev:
                break
            self.recs.append((w, h, units * 8))
            prev = units
            cur += 4
        d = be32(prg, 0x40) - SAT
        backing = be32(prg, d)
        for i in range(len(self.recs)):
            self.streams.append((be32(prg, d + i * 8) - backing, be32(prg, d + i * 8 + 4)))

    def image(self, j):
        im = self.cache.get(j)
        if im is None:
            wf, hf, _ = self.recs[j]
            o, s = self.streams[j]
            im = self.cache[j] = nibbles(decompress_lzss(self.chr[o:o + s]), wf * 2, hf * 2)
        return im

    def frames(self):
        """(flag byte, x, y, image) of every one-part frame, None otherwise."""
        ft, it, p = FRAME_TABLE - SAT, IMAGE_TABLE - SAT, self.prg
        out = []
        for i in range((it - ft) // 4):
            o = be32(p, ft + i * 4) - SAT
            if (be16(p, o) >> 8) & 0x3F != 1:
                out.append(None)
                continue
            out.append((be16(p, o + 4) >> 8, bes16(p, o + 6), bes16(p, o + 8), be16(p, o + 10)))
        return out

    def palette(self, bank):
        t = PALETTE_TABLE - SAT + 2 + bank * 32
        return [be16(self.prg, t + i * 2) for i in range(16)]


def fx_packages(prg, chr_):
    """MAR_W.CHR's sprite packages: {key: (images, palettes, frames)}."""
    def u16(a):
        return be16(prg, a - SAT)
    out, base = {}, 0
    for r in FX_ORDER:
        ra = FX_RES - SAT + r * 12
        im, pal = be32(prg, ra), be32(prg, ra + 4)
        o, recs = im - SAT, []
        while True:
            w, h, u = prg[o], prg[o + 1], be16(prg, o + 2)
            o += 4
            if w == 0 and h == 0:
                size = u * 8
                break
            recs.append((w * 2, h * 2, base + u * 8))
        nb = u16(pal) & 0x3FFF
        pals = [[u16(pal + 2 + (k * 16 + i) * 2) for i in range(16)] for k in range(nb)]
        ftab = pal - FX_NFRAMES[r] * 4
        frames = []
        for f in range(FX_NFRAMES[r]):
            fa = be32(prg, ftab + f * 4 - SAT)
            parts = []
            for p in range((u16(fa) >> 8) & 0x3F):
                q = fa + 4 + p * 8 - SAT
                parts.append((be16(prg, q), bes16(prg, q + 2), bes16(prg, q + 4), be16(prg, q + 6)))
            frames.append(parts)
        imgs = [nibbles(chr_[off:off + ((w * h) >> 1)], w, h) for w, h, off in recs]
        out[r] = (imgs, pals, frames)
        base += size
    if base != len(chr_):
        raise ValueError("MAR_W.CHR size")
    return out


def shared_bank(zero, stage, i):
    """(images, frames by number (empty: none), palettes) of a shared sprite bank."""
    def z(a):
        return a - ZERO

    def recs_of(k):
        a = z(be32(zero, z(SHARED_RES[k])))
        recs = []
        while True:
            rec = (zero[a], zero[a + 1], be16(zero, a + 2))
            a += 4
            recs.append(rec)
            if rec[0] == 0 and rec[1] == 0:
                return recs
    base = 0
    for k in range(i):
        base += recs_of(k)[-1][2] * 8
    recs = recs_of(i)
    imgs = [nibbles(stage[base + o * 8:base + o * 8 + w * h * 2], w * 2, h * 2) for w, h, o in recs[:-1]]
    frames = []
    nf = SHARED_FRAMES.get(i, 0)
    images = be32(zero, z(SHARED_RES[i]))
    for f in range(nf):
        fa = z(be32(zero, z(images - 4 * nf + 4 * f)))
        frames.append([(be16(zero, fa + 4 + p * 8), bes16(zero, fa + 6 + p * 8), bes16(zero, fa + 8 + p * 8),
                        be16(zero, fa + 10 + p * 8)) for p in range((be16(zero, fa) >> 8) & 0x3F)])
    pa = z(be32(zero, z(SHARED_RES[i]) + 4))
    pals = [[be16(zero, pa + 2 + (k * 16 + c) * 2) for c in range(16)] for k in range(be16(zero, pa) & 0x3FFF)]
    return imgs, frames, pals


def fx_frame(imgs, parts):
    boxes = [(x - imgs[j].w // 2, y - imgs[j].h // 2, imgs[j].w, imgs[j].h) for _, x, y, j in parts]
    x0, y0 = min(b[0] for b in boxes), min(b[1] for b in boxes)
    x1, y1 = max(b[0] + b[2] for b in boxes), max(b[1] + b[3] for b in boxes)
    out = Img(y1 - y0, x1 - x0)
    banks = []
    for k, (attr, _, _, j) in enumerate(parts):
        img = imgs[j]
        if attr & 0x10:
            img = cols(img, list(range(img.w - 1, -1, -1)))
        if attr & 0x20:
            f = Img(img.h, img.w)
            for y in range(img.h):
                f.px[y * img.w:(y + 1) * img.w] = img.px[(img.h - 1 - y) * img.w:(img.h - y) * img.w]
            img = f
        blit(out, img, boxes[k][1] - y0, boxes[k][0] - x0, True)
        if attr >> 8 not in banks:
            banks.append(attr >> 8)
    if len(banks) != 1:
        raise ValueError("fx frame banks")
    c, cx, cy = crop(narrow(out, x0, PHASE))
    kept = kept_cols(x0, x1 - x0)
    return c, mapcol(kept[0]) + cx, y0 + cy, banks[0]


class Arrays:
    """Her arrays by C symbol: (element size, values)."""

    def __init__(self):
        self.a = {}

    def put(self, name, size, values):
        if name in self.a:
            raise ValueError("duplicate " + name)
        self.a[name] = (size, values)


def gen_fx(H, prg, pk):
    W = FX_VRAM_W * 4
    atlas = Img(256, W)
    shelf_x = shelf_y = shelf_h = 0
    placed = {}
    for name, r, frames in FX_BANKS:
        imgs, _, sframes = pk[r]
        for f in range(max(frames) + 1):
            if f not in frames or not sframes[f]:
                continue
            img, x, y, bank = fx_frame(imgs, sframes[f])
            clut = next((i for i, (pr, pb, _) in enumerate(FX_PALS) if pr == r and pb == bank), -1)
            if clut < 0:
                raise ValueError(f"fx clut {r} {f}")
            w, h = img.w, img.h
            key = (img.w, bytes(img.px))
            if key not in placed:
                if shelf_x + w > W:
                    shelf_x, shelf_y, shelf_h = 0, shelf_y + shelf_h, 0
                if (FX_VRAM_Y & 255) + shelf_y + h > 255:
                    raise ValueError("fx atlas v")
                blit(atlas, img, shelf_y, shelf_x)
                placed[key] = (shelf_x, shelf_y)
                shelf_x += w
                shelf_h = max(shelf_h, h)
            u, v = placed[key]
            u += (FX_VRAM_X & 63) * 4
            v += FX_VRAM_Y & 255
            w, h = min(w, 255 - u), min(h, 255 - v)
            H.put(f"{name}_{f}", 2, [1, 0, x, y, w, h, clut, FX_TILESET, u, v, u + w, v + h])
    px = pack_psx(sub(atlas, 0, shelf_y + shelf_h, 0, W))
    H.put("mar_fx_lz", 1, list(mb_lzss(px)))
    H.put("mar_fx_pal_ids", 2, [p[2] for p in FX_PALS] + [FLAME_PAL[0]])
    rows = []
    for r, k, _ in FX_PALS:
        rows += [ps1_color(c, i) for i, c in enumerate(pk[r][1][k])]
    rows += FLAME_PAL[1]
    H.put("mar_fx_pal", 2, rows)
    charge = []
    for k in range(5, 20):
        a = CHARGE_PALS + k * 32 - SAT
        charge += [ps1_color(be16(prg, a + i * 2), i) for i in range(16)]
    H.put("mar_charge_pal", 2, charge)


def sp_narrow(im):
    return cols(im, [c for c in range(im.w) if c % 5 != 4])


def by_size(used):
    """Keys, tallest first, then widest, then in insertion order."""
    keys = list(used)
    return [k for _, k in sorted(enumerate(keys), key=lambda e: (-used[e[1]].h, -used[e[1]].w, e[0]))]


def gen_sp(H, pk, zero, stage):
    d_imgs, _, d_pals = shared_bank(zero, stage, 4)
    p_imgs, p_frames, _ = shared_bank(zero, stage, 9)
    b7 = shared_bank(zero, stage, 7)[2]
    pk["S9"] = (p_imgs, [b7[0x1C]], [p_frames[f] if f < len(p_frames) else [] for f in range(15)])
    pk["S4"] = (d_imgs, [d_pals[9]], [[]] + [[(0, 0, 0, 3 + k)] for k in range(1, 11)])
    W = FX_VRAM_W * 4

    def layout(banks, block):
        bx, by = block
        ytop = by & 255
        if not ytop:
            raise ValueError("v 0")
        used = {}
        for _, r, frames, _ in banks:
            imgs, _, sframes = pk[r]
            for f in frames:
                for _, _, _, j in sframes[f]:
                    im = sp_narrow(imgs[j])
                    if f"{r},{j}" in SP_TRANSPOSE:
                        im = transpose(im)
                    used[f"{r},{j}"] = im
        atlas = Img(256, W)
        where = {}
        sky = [1] * (W - 1)
        for k in by_size(used):
            im = used[k]
            best = None
            for x in range(U_FIRST, W - im.w):
                top = max(sky[x:x + im.w])
                if best is None or top < best[0]:
                    best = (top, x)
            if best is None:
                raise ValueError("sp image too wide")
            top, x = best
            blit(atlas, im, top, x)
            where[k] = (x, top)
            for c in range(x, x + im.w):
                sky[c] = top + im.h
        hh = max(sky)
        if ytop + hh > 255:
            raise ValueError("sp block rows")
        for name, r, frames, (foff, coff) in banks:
            imgs, _, sframes = pk[r]
            for f in frames:
                if not sframes[f]:
                    continue
                vals = [len(sframes[f])]
                for attr, x, y, j in sframes[f]:
                    w0 = imgs[j].w
                    im = used[f"{r},{j}"]
                    left = r08(x - w0 / 2)
                    top = y - im.h // 2
                    u, v = where[f"{r},{j}"]
                    u += (bx & 63) * 4
                    v += ytop
                    flags = (2 if attr & 0x10 else 0) | (1 if attr & 0x20 else 0)
                    vals += [flags, left, top, im.w, im.h, (attr >> 8) + coff, tileset(bx, by), u, v, u + im.w, v + im.h]
                H.put(f"{name}_{f + foff}", 2, vals)
        return sub(atlas, 0, hh, 0, W), hh

    def chunks(tag, atlas, block):
        rows = (SP_CHUNK * 2) // W
        res, k, r0 = [], 0, 0
        while r0 < atlas.h:
            part = sub(atlas, r0, min(r0 + rows, atlas.h), 0, W)
            px = pack_psx(part)
            cname = f"mar_sp_lz_{tag}_{k}"
            H.put(cname, 1, list(mb_lzss(px)))
            res.append((cname, block[0], block[1] + r0, part.h, len(px)))
            k += 1
            r0 += rows
        return res

    def strip(b):
        return (b[0], b[1], b[2], b[3])
    atlas, _ = layout([strip(b) for b in SP_PERM], SP_PERM_VRAM)
    perm = chunks("perm", atlas, SP_PERM_VRAM)
    atlas, _ = layout([strip(SP_PUFF)], SP_PUFF_VRAM)
    perm += chunks("puff", atlas, SP_PUFF_VRAM)
    groups = []
    for g, (name, r, frames) in enumerate(SP_GROUPS):
        a, hg = layout([(name, r, frames, (0, 0))], SP_SLOT_VRAM)
        if hg > SP_SLOT_ROWS:
            raise ValueError("sp slot rows " + name)
        groups.append(chunks(str(g), a, SP_SLOT_VRAM))
    # Byakko's flames
    fimgs, fframes, _ = shared_bank(zero, stage, 11)
    used = {}
    for f in range(1, 8):
        for _, _, _, j in fframes[f]:
            used[j] = sp_narrow(fimgs[j])
    bins = [(SP_SLOT_VRAM, SP_SLOT_ROWS), (SP_FLAME_VRAM, 255 - (SP_FLAME_VRAM[1] & 255))]
    atl = [Img(n, W) for _, n in bins]
    where = {}
    shelves = [[] for _ in bins]
    for j in by_size(used):
        im = used[j]
        spot = None
        for bi in range(len(bins)):
            for sh in shelves[bi]:
                if sh[1] >= im.h and sh[2] + im.w <= W - 1:
                    spot = (bi, sh)
                    break
            if spot:
                break
            top = 1 + sum(q[1] for q in shelves[bi])
            if top + im.h <= bins[bi][1]:
                shelves[bi].append([top, im.h, U_FIRST])
                spot = (bi, shelves[bi][-1])
                break
        if not spot:
            raise ValueError("flames do not fit")
        bi, sh = spot
        blit(atl[bi], im, sh[0], sh[2])
        where[j] = (bi, sh[2], sh[0])
        sh[2] += im.w
    for f in range(1, 8):
        vals = [len(fframes[f])]
        for attr, x, y, j in fframes[f]:
            h, w0, w = fimgs[j].h, fimgs[j].w, used[j].w
            bi, u, v = where[j]
            fx, fy = bins[bi][0]
            u += (fx & 63) * 4
            v += fy & 255
            flags = (2 if attr & 0x10 else 0) | (1 if attr & 0x20 else 0)
            vals += [flags, r08(x - w0 / 2), y - h // 2, w, h, 0, tileset(fx, fy), u, v, u + w, v + h]
        H.put(f"mar_fxbank_flame_{f}", 2, vals)
    fl = []
    for k, (blk, _) in enumerate(bins):
        rows_used = max([v + used[j].h for j, (bi, _, v) in where.items() if bi == k] or [0])
        if rows_used:
            fl += chunks(f"flame{k}", sub(atl[k], 0, rows_used, 0, W), blk)
    groups.append(fl)
    first = [0, len(perm)]
    for g in groups:
        first.append(first[-1] + len(g))
    H.put("mar_sp_first", 1, first)
    ids, rows = [], []
    for _, r, _, _, pals in SP_PERM + [SP_PUFF]:
        for k, pid in enumerate(pals):
            ids.append(pid)
            rows += [ps1_color(c, i) for i, c in enumerate(pk[r][1][k])]
    H.put("mar_sp_perm_pal_ids", 2, ids)
    H.put("mar_sp_perm_pal", 2, rows)
    gp = []
    for _, r, _ in SP_GROUPS:
        p = pk[r][1]
        for q in (p + p)[:2]:
            gp += [ps1_color(c, i) for i, c in enumerate(q)]
    fpal = shared_bank(zero, stage, 7)[2]
    for q in (fpal[12], fpal[5]):
        gp += [ps1_color(c, i) for i, c in enumerate(q)]
    H.put("mar_sp_group_pal", 2, gp)


def sat_anims(prg):
    """{address: [(duration, pose)...]} with the control entry."""
    o, end, out = ANIMATION_START - SAT, ANIMATION_END - SAT, {}
    while o + 4 <= end:
        start, pairs = o, []
        while o + 4 <= end:
            d, q = be16(prg, o), be16(prg, o + 2)
            o += 4
            pairs.append((d, q))
            if d in (0, 0xFFFE, 0xFFFF):
                break
        out[SAT + start] = pairs
    return out


def generate(read_saturn, read_ps1):
    H = Arrays()
    prg = read_saturn("MARIA.PRG")
    s = MariaSaturn(prg, read_saturn("MARIA.CHR"))
    frames = s.frames()
    first = {}
    for fr in frames:
        if fr and fr[3] not in first:
            first[fr[3]] = fr
    # sprites: (header + packed bytes, raw size, x0, y0)
    sprites = []
    for j in range(len(s.recs)):
        img = s.image(j)
        fr = first.get(j)
        left = fr[1] - img.w // 2 if fr else 0
        c, x0, y0 = crop(narrow(img, left, PHASE))
        px = pack_psx(c)
        sprites.append(([c.w, c.h, 0, 0] + list(mb_lzss(px)), len(px), x0, y0))
        if c.w > 252 or c.h > 255:
            raise ValueError("sprite size")
    fr_out = []
    for fr in frames:
        if not fr:
            fr_out.append(None)
            continue
        fl, x, y, j = fr
        im = s.image(j)
        left = x - im.w // 2
        _, _, x0, y0 = sprites[j]
        fr_out.append((j, mapcol(kept_cols(left, im.w)[0]) + x0, y - im.h // 2 + y0, 0, fl))
    # hitboxes
    hb = []
    o = HITBOX_TABLE - SAT
    while o + 4 <= PALETTE_TABLE - SAT:
        hb += [r08(s8(prg, o)), s8(prg, o + 1), r08(s8(prg, o + 2)), s8(prg, o + 3)]
        o += 4
    # animations
    anims = sat_anims(prg)
    stand_pose = anims[STAND][0][1]
    ric = read_ps1("BIN/RIC.BIN")

    def flat(pairs):
        return [v for p in pairs for v in p]
    groups = [be32(prg, ANIM_GROUPS - SAT + k * 4) for k in range(14)]
    rev = {}
    for name, addr in ANIM_MAP_ORDER + EXTRA_ANIMS:
        rev.setdefault(addr, name)
    extra = list(EXTRA_ANIMS)
    for addr in groups:
        if addr not in rev:
            name = f"mar_anim_grp_{addr:X}"
            rev[addr] = name
            extra.append((name, addr))
    for src in PL_ANIMS:
        if len(src) == 1:
            H.put(src[0], 1, hb)
        elif len(src) == 2:
            H.put(src[0], 2, flat(anims[src[1]]))
        else:
            name, off, n = src
            pairs = []
            for k in range(n):
                d = ric[off + 4 * k] | (ric[off + 4 * k + 1] << 8)
                q = ric[off + 4 * k + 2] | (ric[off + 4 * k + 3] << 8)
                pairs.append((d, 2 if d == 0xFFFE else q if d in (0, 0xFFFF) else stand_pose))
            H.put(name, 2, flat(pairs))
    jump_ends = {e[0] for e in EXTRA_ANIMS if e[0].startswith("mar_anim_sp_")}
    for name, addr in extra:
        pairs = anims[addr]
        if name in jump_ends:
            pairs = [(0xFFFF, 0) if d == 0xFFFE else (d, q) for d, q in pairs]
        H.put(name, 2, flat(pairs))
    # effects and specials
    pk = fx_packages(prg, read_saturn("MAR_W.CHR"))
    gen_fx(H, prg, pk)
    gen_sp(H, pk, read_saturn("0.BIN"), read_saturn("STAGE_01.CHR"))
    # sprites
    H.put("mar_lz_size", 2, [sp[1] for sp in sprites])
    for j, sp in enumerate(sprites):
        H.put(f"mar_lz_{j}", 1, sp[0])
    for f, fr in enumerate(fr_out):
        if fr:
            H.put(f"spritebank0_{f}", 2, [fr[0] | 0x8000, fr[1], fr[2], fr[3]])
    light = [0] * ((len(fr_out) + 7) // 8)
    for f, fr in enumerate(fr_out):
        if fr and fr[4] == 1:
            light[f >> 3] |= 1 << (f & 7)
    H.put("mar_pal", 2, [ps1_color(c, i) for i, c in enumerate(s.palette(0))])
    H.put("mar_pal_light", 2, [ps1_color(c, i) for i, c in enumerate(s.palette(1))])
    H.put("mar_frame_light", 1, light)
    H.put("mar_hud_vram", 2, hud_vram(prg, read_saturn("MAR_W.CHR")))  # ours: characters/maria-saturn/coop_sat_hud.c
    return H.a


# Her Saturn HUD's art (mar_hud.ts / gen_mar_hud.py): MAR_W.CHR package 5, in VRAM (544, 392),
# 32 x 96 halfwords (F_GAME2's empty tpage 0x18 u128-255 v136-231). Her code uploads it.
HUD_U, HUD_V, HUD_W, HUD_H = 128, 136, 128, 96
PLATE_DROP = {12, 13, 14, 15, 16, 44, 48, 58, 59, 60, 61, 62, 63, 77, 78, 79}


def hud_art(prg, chr_):
    """[(u, v, rows)] of her HUD: the holder, the plate, the digits 0-9, the bars."""
    base, img = 0, None
    for r in FX_ORDER:
        o = be32(prg, FX_RES - SAT + r * 12) - SAT
        recs = []
        while True:
            w, h, u = prg[o], prg[o + 1], be16(prg, o + 2)
            o += 4
            if w == 0 and h == 0:
                size = u * 8
                break
            recs.append((w * 2, h * 2, u * 8))
        if r == 5:
            img = []
            for w, h, off in recs:
                d = chr_[base + off:base + off + (w * h) // 2]
                px = [v for b in d for v in (b >> 4, b & 15)]
                img.append((w, h, [px[y * w:(y + 1) * w] for y in range(h)]))
            break
        base += size
    if img is None:
        raise ValueError("mar hud: resource 5")

    def keep(rows, cs):
        return [[row[c] for c in cs] for row in rows]
    hw, _, holder = img[5]
    pw, _, plate = img[0]
    art = [(128, 136, keep(holder, [c for c in range(hw) if (2 + c) % 5 != 4])),
           (168, 136, keep(plate, [c for c in range(pw) if c not in PLATE_DROP]))]
    for n in range(10):
        art.append((168 + 7 * n, 160, keep(img[6 + n][2], range(7))))
    tile = img[17][2]
    row = [tile[0][c] for c in (3, 4, 6, 7)] + [0] + [tile[0][c] for c in (3, 4, 6)]
    art.append((240, 136, [list(row) for _ in range(96)]))
    if len(art[0][2][0]) != 38 or len(art[1][2][0]) != 64:
        raise ValueError("mar hud: widths")
    return art


def hud_vram(prg, chr_):
    """Her HUD as VRAM halfwords, row by row (RECT 544, 392, 32, 96)."""
    px = {}
    for u, v, rows in hud_art(prg, chr_):
        for y, row in enumerate(rows):
            for x, c in enumerate(row):
                px[(u + x, v + y)] = c
    out = []
    for vy in range(HUD_V, HUD_V + HUD_H):
        for hx in range(32, 64):
            out.append(sum(px.get((hx * 4 + k, vy), 0) << (4 * k) for k in range(4)))
    return out


def array_bytes(size, values):
    """An array as compiled: little-endian elements of that size."""
    if size == 1:
        return bytes(v & 0xFF for v in values)
    if size == 2:
        return b"".join((v & 0xFFFF).to_bytes(2, "little") for v in values)
    return b"".join((v & 0xFFFFFFFF).to_bytes(4, "little") for v in values)


def arrays(read_saturn, read_ps1):
    """{C symbol: its bytes in her overlay}."""
    return {name: array_bytes(size, values) for name, (size, values) in generate(read_saturn, read_ps1).items()}
