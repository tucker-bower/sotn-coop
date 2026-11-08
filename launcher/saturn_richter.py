"""Ultimate Richter's long coat, from the player's own Saturn and PlayStation discs
(docs/design/character-mods.md, D184).

    ric2(ric, read_saturn, f_game2) -> bytes     RIC.BIN with the Saturn's coat

The Saturn has a second Richter (RICHTER2.PRG/CHR, RIC_W2.CHR): the same code and animations,
redrawn in a long blue coat. SOTN Ultimate's RIC2.BIN is the PS1's RIC.BIN with only its sprite
sheet replaced by that art, narrowed to PS1 proportions and placed on the PS1 sprites, plus a block
at the sheet's end (magic "RIC2") of recoloured palettes and the coat-sleeved whip arm, which the
co-op module uploads after his load (module/character.c RicCoatApply). A line-by-line port of
SOTN Ultimate's builder (mods/sotn-ultimate/tools/builder/src/ric2.ts makeRic2 at df11991, by
renanbianchi, AGPL-3.0; itself a byte-exact port of its build_ric2.py). Pure Python.
"""

import struct

from saturn_maria import decompress_lzss

RAM = 0x8013C000
SAT = 0x060A5000
MAGIC = 0x32434952  # "RIC2"
SHEET_END = 0x170AC
MAX_W = MAX_H = 64
RICHTER_SPRITES, SPRITEBANK0, SPRITEBANK1 = 0x8013C020, 0x801530AC, 0x80153AA0  # retail RIC.BIN
P1 = (0x060C12EC, 0x060C0F98, 0x060C0240, "RICHTER.PRG", "RICHTER.CHR")
P2 = (0x060C120C, 0x060C0EA0, 0x060C0240, "RICHTER2.PRG", "RICHTER2.CHR")
# (PS1 rect (u0, v0, u1, v1), RIC_W2 offset, stride, phase, x offset[, y offset, image height])
ARMS = [
    (112, 16, 128, 32, 21350, 24, 3, -2), (112, 0, 128, 16, 21508, 24, 1, -5), (64, 48, 88, 64, 21660, 24, 0, 5),
    (88, 48, 112, 64, 0x5540, 32, 3, 2, 4, 9), (80, 32, 96, 48, 21970, 24, 3, -2), (112, 32, 128, 56, 22136, 16, 3, 2),
    (96, 32, 112, 48, 22286, 16, 3, -2), (96, 16, 112, 32, 22414, 16, 1, -2), (96, 0, 112, 16, 22504, 16, 3, 1),
]
ARM_VRAM = (0x240, 0x180)


def be16(d, o):
    return (d[o] << 8) | d[o + 1]


def bes16(d, o):
    v = be16(d, o)
    return v - 0x10000 if v & 0x8000 else v


def be32(d, o):
    return (d[o] << 24) | (d[o + 1] << 16) | (d[o + 2] << 8) | d[o + 3]


def le16(d, o):
    return d[o] | (d[o + 1] << 8)


def les16(d, o):
    v = le16(d, o)
    return v - 0x10000 if v & 0x8000 else v


def le32(d, o):
    return struct.unpack_from("<I", d, o)[0]


def check(ok, what):
    if not ok:
        raise ValueError("ric2: " + what)


class Img:
    """A 4bpp image as colour indices, row-major."""
    __slots__ = ("w", "h", "d")

    def __init__(self, w, h, d=None):
        self.w, self.h = w, h
        self.d = d if d is not None else bytearray(w * h)

    def at(self, y, x):
        return self.d[y * self.w + x]

    def cols(self, cs):
        o = Img(len(cs), self.h)
        for y in range(self.h):
            row = self.d[y * self.w:(y + 1) * self.w]
            o.d[y * o.w:(y + 1) * o.w] = bytes(row[c] for c in cs)
        return o

    def nonzero(self):
        return sum(1 for v in self.d if v)


def unpack_psx(data, o, w, h):
    img = Img(w, h)
    for i in range((w * h) >> 1):
        img.d[2 * i] = data[o + i] & 15
        img.d[2 * i + 1] = data[o + i] >> 4
    return img


def pack_psx(img):
    d = img.d
    return bytes((d[2 * i] | (d[2 * i + 1] << 4)) & 0xFF for i in range(len(d) >> 1))


class Saturn:
    def __init__(self, profile, prg, chr_):
        self.image_table, self.frame_table, self.palette_table = profile[:3]
        self.prg, self.chr, self.cache = prg, chr_, {}
        self.recs, cursor, prev = [], self.image_table - SAT, -1
        while cursor + 4 <= len(prg):
            dims, units = be16(prg, cursor), be16(prg, cursor + 2)
            w, h = dims >> 8, dims & 0xFF
            if not w or not h or w > 128 or h > 128 or units < prev:
                break
            self.recs.append((w, h, units * 8))
            prev = units
            cursor += 4
        d = be32(prg, 0x40) - SAT
        backing = be32(prg, d)
        self.streams = [(be32(prg, d + i * 8) - backing, be32(prg, d + i * 8 + 4)) for i in range(len(self.recs))]

    def image(self, j):
        if j not in self.cache:
            wf, hf, _ = self.recs[j]
            o, s = self.streams[j]
            d = decompress_lzss(self.chr[o:o + s])
            w, h = wf * 2, hf * 2
            n = (w * h) >> 1
            check(len(d) >= n, f"short Saturn image {j}")
            img = Img(w, h)
            for i in range(n):
                img.d[2 * i] = d[i] >> 4
                img.d[2 * i + 1] = d[i] & 15
            self.cache[j] = img
        return self.cache[j]

    def frames(self):
        ft, it, p = self.frame_table - SAT, self.image_table - SAT, self.prg
        out = []
        for i in range((it - ft) // 4):
            o = be32(p, ft + i * 4) - SAT
            if (be16(p, o) >> 8) & 0x3F != 1:
                out.append(None)
                continue
            out.append((be16(p, o + 4) >> 8, bes16(p, o + 6), bes16(p, o + 8), be16(p, o + 10)))
        return out

    def palette(self, bank):
        t = self.palette_table - SAT + 2 + bank * 32
        return [be16(self.prg, t + 2 * i) for i in range(16)]


def narrow(img, left, phase, rescue):
    w = img.w
    out = img.cols([c for c in range(w) if (left + c) % 5 != phase])
    if rescue:
        for c in range(w):
            if (left + c) % 5 != phase:
                continue
            dst = -1
            for y in range(img.h):
                v = img.at(y, c)
                nl = img.at(y, c - 1) if c > 0 else 0
                nr = img.at(y, c + 1) if c + 1 < w else 0
                if v != 0 and nl == 0 and nr == 0:
                    if dst < 0:
                        k = sum(1 for cc in range(c) if (left + cc) % 5 != phase)
                        dst = min(max(k - 1, 0), out.w - 1)
                        check(dst >= 0, "narrow: empty image")
                    out.d[y * out.w + dst] = v
    return out


def dropped_between(a, b, phase):
    if b >= a:
        return b - a - sum(1 for x in range(a, b) if x % 5 == phase)
    return -dropped_between(b, a, phase)


def place_score(ps, nr, nr_count, ox, oy):
    mism = inside = 0
    pw, nw = ps.w, nr.w
    for y in range(ps.h):
        ny = y - oy
        row_in = 0 <= ny < nr.h
        prow = ps.d[y * pw:(y + 1) * pw]
        for x in range(pw):
            nx = x - ox
            b = nr.d[ny * nw + nx] if row_in and 0 <= nx < nw else 0
            if b:
                inside += 1
            if prow[x] != b:
                mism += 1
    return mism + nr_count - inside


def align(ps, sat):
    """Best (mismatch, phase relative to the image, ox, oy)."""
    best = None
    for ph in range(5):
        nr = sat.cols([c for c in range(sat.w) if c % 5 != ph])
        cnt = nr.nonzero()
        for oy in range(-4, 5):
            for ox in range(-10, 11):
                s = place_score(ps, nr, cnt, ox, oy)
                if best is None or s < best[0]:
                    best = (s, ph, ox, oy)
    return best


def crop(img):
    x0 = y0 = 1 << 30
    x1 = y1 = -1
    for y in range(img.h):
        for x in range(img.w):
            if img.at(y, x):
                x0, x1, y0, y1 = min(x0, x), max(x1, x), min(y0, y), max(y1, y)
    if y1 < 0:
        return Img(min(4, img.w), min(1, img.h)), 0, 0
    cw = x1 + 1 - x0
    w = (cw + 3) & ~3
    c = Img(w, y1 + 1 - y0)
    for y in range(c.h):
        for x in range(cw):
            c.d[y * w + x] = img.at(y0 + y, x0 + x)
    return c, x0, y0


def largest_component(img):
    """The largest 8-connected component (the first found of the largest size)."""
    w, h = img.w, img.h
    seen = bytearray(w * h)
    best = []
    for y in range(h):
        for x in range(w):
            if img.at(y, x) and not seen[y * w + x]:
                comp, stack = [], [y * w + x]
                seen[y * w + x] = 1
                while stack:
                    p = stack.pop()
                    comp.append(p)
                    cy, cx = divmod(p, w)
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            ny, nx = cy + dy, cx + dx
                            if 0 <= ny < h and 0 <= nx < w and img.at(ny, nx) and not seen[ny * w + nx]:
                                seen[ny * w + nx] = 1
                                stack.append(ny * w + nx)
                if len(comp) > len(best):
                    best = comp
    out = Img(w, h)
    for p in best:
        out.d[p] = img.d[p]
    return out


def retail_pal(g2, k):
    return [le16(g2, 0x40000 + (k - 0x100) * 32 + 2 * i) for i in range(16)]


def ric2(ric, read_saturn, g2):
    """RIC.BIN (retail) -> RIC2.BIN: his sheet in the coat, and its palettes and arms block."""
    w2 = read_saturn("RIC_W2.CHR")
    s1 = Saturn(P1, read_saturn(P1[3]), read_saturn(P1[4]))
    s2 = Saturn(P2, read_saturn(P2[3]), read_saturn(P2[4]))
    check(SPRITEBANK0 - RAM == SHEET_END, "RIC's sprite sheet moved")
    table = RICHTER_SPRITES - RAM
    ptrs, min_ptr, o = [], 1 << 40, table
    while True:
        p = le32(ric, o)
        if not (RAM <= p < RAM + SHEET_END) or (ptrs and o >= min_ptr - RAM):
            break
        ptrs.append(p)
        min_ptr = min(min_ptr, p)
        o += 4
    data_start = table + 4 * len(ptrs)
    sprites = []
    for p in ptrs:
        q = p - RAM
        w, h, px, py = ric[q], ric[q + 1], ric[q + 2], ric[q + 3]
        sprites.append((w, h, px, py, unpack_psx(ric, q + 4, w, h), q))
    frames = []
    o, lim = SPRITEBANK0 - RAM, SPRITEBANK1 - RAM
    while o < lim:
        p = le32(ric, o)
        if p == 0:
            frames.append(None)
        else:
            q = p - RAM
            lim = min(lim, q)
            frames.append((le16(ric, q) & 0x7FFF, les16(ric, q + 2), les16(ric, q + 4), les16(ric, q + 6), q))
        o += 4
    f1, f2 = s1.frames(), s2.frames()
    check(len(frames) == len(f1), f"frame count {len(frames)} {len(f1)}")
    delta, cand = {}, {}
    for f, fr in enumerate(frames):
        if fr is None:
            continue
        a, b = f1[f], f2[f]
        check(a is not None and b is not None and a[3] == b[3], f"frame {f}")
        j = a[3]
        cand.setdefault(fr[0], set()).add(j)
        i1, i2 = s1.image(j), s2.image(j)
        e = (a[1] - i1.w // 2, a[2] - i1.h // 2, b[1] - i2.w // 2, b[2] - i2.h // 2)
        k = (e[2] - e[0], e[3] - e[1])
        if j in delta:
            check(delta[j][1] == k, f"inconsistent {j}")
        else:
            delta[j] = (e, k)
    groups = {}
    for i, s in enumerate(sprites):
        groups.setdefault(s[5], []).append(i)
    new_img, frame_fix = {}, {}
    for off in sorted(groups):
        members = groups[off]
        _, h, px, py, ps, _ = sprites[members[0]]
        js = set()
        for i in members:
            js |= cand.get(i, set())
        best = None
        for j in sorted(js):
            r = align(ps, s1.image(j))
            if best is None or r[0] < best[0][0]:
                best = (r, j)
        if best is None or best[0][0] > 0.15 * ps.nonzero():
            # placeholder art: the Saturn image it is a copy of
            for j in range(len(s1.recs)):
                if abs(s1.image(j).h - h) > 4:
                    continue
                r = align(ps, s1.image(j))
                if best is None or r[0] < best[0][0]:
                    best = (r, j)
        (_, ph, ox, oy), j = best
        check(j in delta, f"no Saturn placement for image {j}")
        left1, top1, left2, top2 = delta[j][0]
        phase = (left1 + ph) % 5
        img2 = narrow(s2.image(j), left2, phase, True)
        dx = dropped_between(left1, left2, phase)
        dy = top2 - top1
        c, cx, cy = crop(img2)
        check(c.w <= MAX_W and c.h <= MAX_H, f"sprite too big {members}")
        npx, npy = px + ox + dx + cx, py + oy + dy + cy
        fx = fy = 0
        if not 0 <= npx <= 255:
            fx = npx if npx < 0 else npx - 255
            npx -= fx
        if not 0 <= npy <= 255:
            fy = npy if npy < 0 else npy - 255
            npy -= fy
        if fx or fy:
            for fr in frames:
                if fr and fr[0] in members:
                    frame_fix[fr[4]] = (fx, fy)
        new_img[off] = bytes((c.w, c.h, npx, npy)) + pack_psx(c)
    # palettes
    base = retail_pal(g2, 0x120)
    r1b0, r2b0 = s1.palette(0), s2.palette(0)
    for i in range(1, 16):
        check((base[i] & 0x7FFF) == (r1b0[i] & 0x7FFF), "PAL_RICHTER is not RICHTER's bank 0")
    sat_bank = {0x12B: 2, 0x12C: 3, 0x12D: 4, 0x12E: 6}
    pals = []
    for k in range(0x100, 0x200):
        p = retail_pal(g2, k)
        same = [i for i in range(1, 16) if (p[i] & 0x7FFF) == (base[i] & 0x7FFF)]
        if len(same) < 10:
            continue
        q = list(p)
        for i in same:
            q[i] = (r2b0[i] & 0x7FFF) | (p[i] & 0x8000)
        if q != p:
            pals.append((k, q if k not in sat_bank else [q[0]] + s2.palette(sat_bank[k])[1:]))
    # whip-brandish arms
    arms = []
    for arm in ARMS:
        u0, v0, u1, v1, o, stride, ph, ox = arm[:8]
        h, w = v1 - v0, u1 - u0
        oy, ih = (arm[8], arm[9]) if len(arm) > 8 else (0, h)
        sat = Img(stride, ih)
        for i in range((ih * stride) >> 1):
            sat.d[2 * i] = w2[o + i] >> 4
            sat.d[2 * i + 1] = w2[o + i] & 15
        nr = largest_component(narrow(sat, 0, ph, True))
        out = Img(w, h)
        for y in range(ih):
            for x in range(nr.w):
                v = nr.at(y, x)
                if v and 0 <= x + ox < w and 0 <= y + oy < h:
                    out.d[(y + oy) * w + x + ox] = v
        arms.append(((ARM_VRAM[0] + u0 // 4, ARM_VRAM[1] + v0, w >> 2, h), out))
    # the file
    out = bytearray(ric)
    end = SHEET_END - 8
    pos, written, addr = data_start, {}, {}
    for off in sorted(new_img):
        b = new_img[off]
        if b not in written:
            written[b] = pos
            out[pos:pos + len(b)] = b
            pos = (pos + len(b) + 3) & ~3
        addr[off] = written[b]
    for i, s in enumerate(sprites):
        struct.pack_into("<I", out, table + 4 * i, RAM + addr[s[5]])
    extra = pos
    blob = bytearray(struct.pack("<I", len(pals)))
    for k, q in pals:
        blob += struct.pack("<I", k) + struct.pack("<16H", *q)
    blob += struct.pack("<I", len(arms))
    for (x, y, w, h), img in arms:
        blob += struct.pack("<4H", x, y, w, h) + pack_psx(img)
        blob += bytes(-len(blob) % 4)
    check(pos + len(blob) <= end, "costume sheet too big")
    out[pos:pos + len(blob)] = blob
    pos += len(blob)
    out[pos:end] = bytes(end - pos)
    struct.pack_into("<II", out, end, MAGIC, RAM + extra)
    for q, (fx, fy) in frame_fix.items():
        struct.pack_into("<hh", out, q + 2, les16(out, q + 2) + fx, les16(out, q + 4) + fy)
    return bytes(out)
