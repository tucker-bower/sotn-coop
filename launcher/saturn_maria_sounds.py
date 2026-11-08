"""Saturn Maria's own voice and sounds, from the player's Saturn and PlayStation discs
(docs/design/character-mods.md, D183).

    banks(read_saturn, read_ps1, progress=None) -> (vh1, vb1, vh2, vb2)

Her two PS1 sound banks, in the slots of Richter's (vab 1, VAB/SD_RIH) and the prologue Maria's
(vab 2, VAB/SD_MAR), which her code's ids (mar_sfx.h) name. Most of her sounds are SEQs of the
Saturn's SD_MARI.CRT, rendered by a small SCSP-style synth; her voice clips are SDE7.PCM's; one is
the PS1 common bank's. A line-by-line port, in pure Python, of SOTN Ultimate's builder
(mods/sotn-ultimate/tools/builder/src/mar_sounds.ts, saturn_sfx.ts, vab.ts, dsp.ts at df11991, by
renanbianchi, AGPL-3.0), and of its tools/satxa.c VAG encoder. read_saturn(path) gives a Saturn disc
file (0.BIN, SD/SD_MARI.CRT...); read_ps1(path) a PS1 one (DRA.BIN, VAB/SD_RIH.VH, SD_J010.VH...).
Slow-ish (it synthesizes and encodes a few hundred thousand samples): made once, when the player
adds their Saturn disc.
"""

import math
import struct

# ---------------------------------------------------------------- dsp (dsp.ts)


def clamp16(x):
    return -32768 if x < -32768 else 32767 if x > 32767 else x


def lround(x):
    """C's lround: half away from zero."""
    return int(math.floor(x + 0.5)) if x >= 0 else -int(math.floor(-x + 0.5))


def _pairwise(a, lo, n):
    if n < 8:
        r = -0.0
        for i in range(n):
            r += a[lo + i]
        return r
    if n <= 128:
        r = [a[lo + j] for j in range(8)]
        i = 8
        while i < n - (n % 8):
            for j in range(8):
                r[j] += a[lo + i + j]
            i += 8
        res = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]))
        while i < n:
            res += a[lo + i]
            i += 1
        return res
    n2 = n // 2
    n2 -= n2 % 8
    return _pairwise(a, lo, n2) + _pairwise(a, lo + n2, n - n2)


def np_sum(a):
    """np.sum of float64s: the first element, then numpy's pairwise sum of the rest."""
    return a[0] + _pairwise(a, 1, len(a) - 1) if len(a) else 0


def np_linspace(start, stop, num):
    if num == 0:
        return []
    div = num - 1
    delta = stop - start
    step = delta / div if div > 0 else 0
    out = [(i * step + start if div > 0 and step != 0 else (i / div) * delta + start if div > 0 else start)
           for i in range(num)]
    if num > 1:
        out[-1] = stop
    return out


def np_interp(x, xp, fp):
    out, n, j = [], len(xp), 0
    for v in x:
        if v <= xp[0]:
            out.append(fp[0])
            continue
        if v >= xp[n - 1]:
            out.append(fp[n - 1])
            continue
        if v < xp[j]:
            j = 0
        while j + 1 < n and xp[j + 1] <= v:
            j += 1
        slope = (fp[j + 1] - fp[j]) / (xp[j + 1] - xp[j])
        r = slope * (v - xp[j]) + fp[j]
        if r != r:  # NaN
            r = slope * (v - xp[j + 1]) + fp[j + 1]
            if r != r and fp[j] == fp[j + 1]:
                r = fp[j]
        out.append(r)
    return out


def np_convolve_same(x, h):
    n, m = len(x), len(h)
    start = (n + m - 1 - max(n, m)) // 2
    out = []
    for k in range(max(n, m)):
        i = k + start
        s = 0
        for j in range(min(i, m - 1), max(0, i - n + 1) - 1, -1):
            s += x[i - j] * h[j]
        out.append(s)
    return out


def sinc(x):
    if x == 0:
        return 1
    y = math.pi * x
    return math.sin(y) / y


def hanning(n):
    if n == 1:
        return [1.0]
    return [0.5 + 0.5 * math.cos(math.pi * (1 - n + 2 * i) / (n - 1)) for i in range(n)]


def centre(note, rate, fine=0):
    """The VAB centre note and shift at which `note` plays the sample at its own rate."""
    q = round((note + 12 * math.log2(44100 / rate) - fine / 128.0) * 16)
    c = math.ceil(q / 16)
    return c, (c * 16 - q) * 8


def resample(samples, rate, new_rate):
    """Windowed-sinc lowpass, then linear interpolation."""
    n = int(len(samples) * new_rate / rate)
    cutoff = 0.45 * new_rate / rate
    win = hanning(65)
    h = [2 * cutoff * sinc(2 * cutoff * (i - 32)) * win[i] for i in range(65)]
    s = np_sum(h)
    h = [v / s for v in h]
    y = np_convolve_same(samples, h)
    out = np_interp([i * rate / new_rate for i in range(n)], list(range(len(y))), y)
    return [clamp16(round(v)) for v in out], new_rate

# ---------------------------------------------------------------- VAB (vab.ts)


TONE_FIELDS = [("prior", "B"), ("mode", "B"), ("vol", "B"), ("pan", "B"), ("center", "B"), ("shift", "B"),
               ("min", "B"), ("max", "B"), ("vibW", "B"), ("vibT", "B"), ("porW", "B"), ("porT", "B"),
               ("pbmin", "B"), ("pbmax", "B"), ("r1", "B"), ("r2", "B"), ("adsr1", "H"), ("adsr2", "H"),
               ("prog", "h"), ("vag", "h"), ("r3", "h"), ("r4", "h"), ("r5", "h"), ("r6", "h")]
TONE_FMT = "<" + "".join(f for _, f in TONE_FIELDS)


class Vab:
    """A PS1 sound bank: VH (header, 128 programs, 16 tones each for the used ones, VAG sizes) and
    VB (the sample bodies)."""

    def __init__(self, vh, vb):
        if struct.unpack_from("<I", vh, 0)[0] != 0x56414270:
            raise ValueError("not a VAB header")
        ps, vs = struct.unpack_from("<H", vh, 18)[0], struct.unpack_from("<H", vh, 22)[0]
        self.header = bytes(vh[:32])
        self.programs = [bytes(vh[32 + i * 16:48 + i * 16]) for i in range(128)]
        self.tones = {}
        off = 32 + 128 * 16
        for p in range(128):
            if self.programs[p][0] == 0:
                continue
            self.tones[p] = [dict(zip((n for n, _ in TONE_FIELDS), struct.unpack_from(TONE_FMT, vh, off + t * 32)))
                             for t in range(16)]
            off += 16 * 32
        if len(self.tones) != ps:
            raise ValueError("VAB: program count")
        self.vags, pos = [], 0
        for i in range(1, vs + 1):
            n = struct.unpack_from("<H", vh, off + 2 * i)[0] << 3
            self.vags.append(bytes(vb[pos:pos + n]))
            pos += n
        if len(vh) != off + 512:
            raise ValueError("VAB: header size")

    def write(self):
        progs = sorted(self.tones)
        ps, ts = len(progs), sum(self.programs[p][0] for p in progs)
        vb = b"".join(self.vags)
        vh = bytearray(32 + 128 * 16 + ps * 512 + 512)
        vh[:32] = self.header
        struct.pack_into("<I", vh, 12, len(vh) + len(vb))
        struct.pack_into("<HHH", vh, 18, ps, ts, len(self.vags))
        for p in range(128):
            vh[32 + p * 16:48 + p * 16] = self.programs[p]
        off = 32 + 128 * 16
        for p in progs:
            for tn in self.tones[p]:
                struct.pack_into(TONE_FMT, vh, off, *(tn[n] for n, _ in TONE_FIELDS))
                off += 32
        for i, v in enumerate(self.vags):
            struct.pack_into("<H", vh, off + 2 * (i + 1), len(v) >> 3)
        return bytes(vh), vb

# ---------------------------------------------------------------- VAG encoding (satxa.c cmd_vag)


SPU_K0 = (0, 60, 115, 98, 122)
SPU_K1 = (0, 0, -52, -55, -60)


def _spu_block(x, st):
    """28 samples -> a 16-byte block (flags byte left 0); st = [old, older]."""
    best_f = best_r = 0
    best_err = 1e300
    for f in range(5):
        k0, k1 = SPU_K0[f], SPU_K1[f]
        for r in range(13):
            o, oo = st
            err = 0.0
            m = (1 << r) / 4096.0
            for i in range(28):
                if not err < best_err:
                    break
                pred = (o * k0 + oo * k1 + 32) >> 6
                t = lround((x[i] - pred) * m)
                t = -8 if t < -8 else 7 if t > 7 else t
                s = ((t << 12) >> r) + pred
                s = -32768 if s < -32768 else 32767 if s > 32767 else s
                d = s - x[i]
                err += d * d
                oo, o = o, s
            if err < best_err:
                best_err, best_f, best_r = err, f, r
    out = bytearray(16)
    out[0] = best_f << 4 | best_r
    k0, k1 = SPU_K0[best_f], SPU_K1[best_f]
    m = (1 << best_r) / 4096.0
    for i in range(28):
        pred = (st[0] * k0 + st[1] * k1 + 32) >> 6
        t = lround((x[i] - pred) * m)
        t = -8 if t < -8 else 7 if t > 7 else t
        s = clamp16(((t << 12) >> best_r) + pred)
        out[2 + i // 2] |= (t & 15) << ((i & 1) * 4)
        st[1], st[0] = st[0], s
    return out


def vag(pcm):
    """Mono 16-bit samples -> a VAB sample body: a zero block, the data (first block flag 4, last
    flag 1), then a silent end block (flag 7)."""
    n = len(pcm)
    x = list(pcm) + [0] * 28
    st = [0, 0]
    out = bytearray(16)
    for i in range(0, n, 28):
        b = _spu_block(x[i:i + 28], st)
        b[1] = (4 if i == 0 else 0) | (1 if i + 28 >= n else 0)
        out += b
    end = bytearray(b"\x77" * 16)
    end[0], end[1] = 0, 7
    return bytes(out + end)

# ---------------------------------------------------------------- the synth (saturn_sfx.ts)


ZERO_BASE = 0x06004080
CFG_ADDR, CFG_FIRST, CFG_COUNT = 0x06041655, 0x600, 791
SCSP_RATE = 44100
MIX_GAIN = 0.5
AR_TIMES = [1e9, 1e9, 8100.0, 6900.0, 6000.0, 4800.0, 4000.0, 3400.0, 3000.0, 2400.0, 2000.0, 1700.0, 1500.0,
            1200.0, 1000.0, 860.0, 760.0, 600.0, 500.0, 430.0, 380.0, 300.0, 250.0, 220.0, 190.0, 150.0, 130.0,
            110.0, 95.0, 76.0, 63.0, 55.0, 47.0, 38.0, 31.0, 27.0, 24.0, 19.0, 15.0, 13.0, 12.0, 9.4, 7.9, 6.8,
            6.0, 4.7, 3.8, 3.4, 3.0, 2.4, 2.0, 1.8, 1.6, 1.3, 1.1, 0.93, 0.85, 0.65, 0.53, 0.44, 0.40, 0.35, 0.0, 0.0]
DR_TIMES = [1e9, 1e9, 118200.0, 101300.0, 88600.0, 70900.0, 59100.0, 50700.0, 44300.0, 35500.0, 29600.0,
            25300.0, 22200.0, 17700.0, 14800.0, 12700.0, 11100.0, 8900.0, 7400.0, 6300.0, 5500.0, 4400.0, 3700.0,
            3200.0, 2800.0, 2200.0, 1800.0, 1600.0, 1400.0, 1100.0, 920.0, 790.0, 690.0, 550.0, 460.0, 390.0,
            340.0, 270.0, 230.0, 200.0, 170.0, 140.0, 110.0, 98.0, 85.0, 68.0, 57.0, 49.0, 43.0, 34.0, 28.0, 25.0,
            22.0, 18.0, 14.0, 12.0, 11.0, 8.5, 7.1, 6.1, 5.4, 4.3, 3.6, 3.1]
EG_RANGE_DB = 96.0


def be16(d, o):
    return (d[o] << 8) | d[o + 1]


def be32(d, o):
    return (d[o] << 24) | (d[o + 1] << 16) | (d[o + 2] << 8) | d[o + 3]


def s8(v):
    return v - 256 if v & 0x80 else v


class Layer:
    def __init__(self, bank, o):
        d = bank.data
        self.lo, self.hi = d[o], d[o + 1]
        r0 = be16(d, o + 2)
        self.loop, self.pcm8 = (r0 >> 5) & 3, (r0 >> 4) & 1
        self.sa = ((r0 & 0xF) << 16) | be16(d, o + 4)
        self.lsa, self.lea = be16(d, o + 6), be16(d, o + 8)
        a1, a2 = be16(d, o + 10), be16(d, o + 12)
        self.ar, self.d1r, self.d2r = a1 & 0x1F, (a1 >> 6) & 0x1F, (a1 >> 11) & 0x1F
        self.rr, self.dl, self.krs = a2 & 0x1F, (a2 >> 5) & 0x1F, (a2 >> 10) & 0xF
        self.tl = d[o + 15]
        self.disdl, self.dipan = d[o + 24] >> 5, d[o + 24] & 0x1F
        self.base, self.fine, self.vl_index = d[o + 25], s8(d[o + 26]), d[o + 29]
        n = self.lea + 1
        so = bank.start + self.sa
        if self.pcm8:
            self.samples = [s8(b) / 128.0 for b in d[so:min(len(d), so + n)]]
        else:
            end = min(len(d), so + 2 * n)
            cnt = max(0, (end - so) // 2)
            self.samples = [(((be16(d, so + 2 * i) + 0x8000) & 0xFFFF) - 0x8000) / 32768.0 for i in range(cnt)]


class ToneBank:
    def __init__(self, data, start):
        self.data, self.start = data, start
        d = data
        mix, vl, peg = (be16(d, start + 2 * i) for i in range(3))
        self.vl_tables = [d[start + o:start + o + 10] for o in range(vl, peg, 10)]
        self.voices = []
        for v in range((mix - 8) // 2):
            vo = start + be16(d, start + 8 + 2 * v)
            hdr = d[vo:vo + 4]
            self.voices.append((hdr, [Layer(self, vo + 4 + 32 * i) for i in range(hdr[2] + 1)]))

    def vel_level(self, idx, vel):
        if idx >= len(self.vl_tables):
            return vel
        t = self.vl_tables[idx]
        return np_interp([vel], [0, t[4], t[7], 127], [t[2], t[5], t[8], 127])[0]


def find_tone_bank(d):
    for tb in range(0, len(d) - 64, 2):
        mix, vl, peg, plfo = (be16(d, tb + 2 * i) for i in range(4))
        if not (8 < mix < vl <= peg <= plfo < 0x2000) or mix % 2:
            continue
        nv = (mix - 8) // 2
        offs = [be16(d, tb + 8 + 2 * i) for i in range(nv)]
        if nv < 1 or offs[0] < plfo:
            continue
        if all(offs[i + 1] - offs[i] == 4 + 32 * (d[tb + offs[i] + 2] + 1) for i in range(nv - 1)):
            return tb
    raise ValueError("no tone bank")


class Crt:
    """A .CRT sound bank file: SEQ tables and one tone bank."""

    def __init__(self, data):
        d = self.data = data
        self.tables = {"A": (0, [be32(d, 2 + 4 * i) for i in range(be16(d, 0))])}
        tb = find_tone_bank(d)
        if tb > 0x800 and be16(d, 0x800) and be32(d, 0x802) == 2 + 4 * be16(d, 0x800):
            self.tables["B"] = (0x800, [be32(d, 0x802 + 4 * i) for i in range(be16(d, 0x800))])
        self.tones = ToneBank(d, tb)

    def seq(self, table, idx):
        base, offs = self.tables[table]
        return base + offs[idx] if idx < len(offs) else None


class SfxContext:
    """The banks loaded while a stage plays."""

    def __init__(self, read_saturn, stage="SD_TEI.CRT", player="SD_MARI.CRT", common="SD_JO10.CRT"):
        self.zero = read_saturn("0.BIN")
        self.common, self.player, self.stage = (Crt(read_saturn("SD/" + n)) for n in (common, player, stage))
        self.tone_banks = {0: self.common.tones, 1: self.player.tones, 2: self.stage.tones}

    def locate(self, sid):
        if not CFG_FIRST <= sid < CFG_FIRST + CFG_COUNT:
            raise ValueError(f"Saturn sound id out of range: {sid:x}")
        o = CFG_ADDR - ZERO_BASE + 5 * (sid - CFG_FIRST)
        typ, idx = self.zero[o], self.zero[o + 3]
        c, table = ((self.common, "A"), (self.player, "A"), (self.stage, "A"), (self.stage, "B"))[typ]
        return (c, c.seq(table, idx)) if table in c.tables else (c, None)


GATE_EXT = {0x88: 0x200, 0x89: 0x800, 0x8A: 0x1000, 0x8B: 0x2000}
STEP_EXT = {0x8C: 0x100, 0x8D: 0x200, 0x8E: 0x800, 0x8F: 0x1000}


class Seq:
    def __init__(self, d, s):
        self.resolution = be16(d, s)
        nt, data_off = be16(d, s + 2), be16(d, s + 4)
        self.tempos = [(be32(d, s + 8 + 8 * i), be32(d, s + 12 + 8 * i)) for i in range(nt)]
        self.events = []
        self._parse(d, s + data_off)

    def _parse(self, d, base):
        t = gate_ext = 0
        p, ret = base, None
        while True:
            if ret is not None and ret[1] == 0:
                p, ret = ret[0], None
            b = d[p]
            if ret is not None:
                ret = (ret[0], ret[1] - 1)
            if b < 0x80:
                gate = d[p + 3] + gate_ext + (0x100 if b & 0x40 else 0)
                t += d[p + 4] + (0x100 if b & 0x20 else 0)
                gate_ext = 0
                self.events.append((t, "note", b & 0xF, d[p + 1], d[p + 2], gate))
                p += 5
            elif b == 0x81:
                ret = (p + 4, d[p + 3])
                p = base + be16(d, p + 1)
            elif b == 0x83:
                break
            elif b in GATE_EXT:
                gate_ext += GATE_EXT[b]
                p += 1
            elif b in STEP_EXT:
                t += STEP_EXT[b]
                p += 1
            elif 0xA0 <= b < 0xB0:
                t += d[p + 3]
                p += 4
            elif 0xB0 <= b < 0xC0:
                t += d[p + 3]
                self.events.append((t, "cc", b & 0xF, d[p + 1], d[p + 2]))
                p += 4
            elif 0xC0 <= b < 0xD0:
                t += d[p + 2]
                self.events.append((t, "prog", b & 0xF, d[p + 1]))
                p += 3
            elif 0xD0 <= b < 0xE0:
                t += d[p + 2]
                p += 3
            elif 0xE0 <= b < 0xF0:
                t += d[p + 2]
                self.events.append((t, "bend", b & 0xF, d[p + 1]))
                p += 3
            else:
                break

    def seconds(self, tick):
        sec, t0 = 0.0, 0
        tempos = self.tempos or [(0, 500000)]
        for i, (steps, usec) in enumerate(tempos):
            span = tick - t0 if i == len(tempos) - 1 else min(steps, tick - t0)
            sec += span * usec / 1e6 / self.resolution
            t0 += span
            if t0 >= tick:
                break
        return sec


def eg_rate(r, octave, fns_hi, krs):
    if r == 0:
        return 0
    rate = 2 * r
    if krs != 0xF:
        rate += octave + 2 * krs + fns_hi
    return max(0, min(63, rate))


def envelope(layer, n_on, n_total, sr, octave, fns_hi):
    env = [0.0] * n_total
    ar = eg_rate(layer.ar, octave, fns_hi, layer.krs)
    d1 = eg_rate(layer.d1r, octave, fns_hi, layer.krs)
    d2 = eg_rate(layer.d2r, octave, fns_hi, layer.krs)
    rr = eg_rate(layer.rr, octave, fns_hi, layer.krs)
    att = 0.0
    a_step = 1.0 / max(1.0, AR_TIMES[ar] * sr / 1000.0) if AR_TIMES[ar] < 1e8 else 0.0
    if ar >= 62 or AR_TIMES[ar] == 0.0:
        att = 1.0

    def dstep(rate):
        tm = DR_TIMES[rate]
        return 0.0 if tm >= 1e8 else EG_RANGE_DB / (tm * sr / 1000.0)
    s1, s2, s_r = dstep(d1), dstep(d2), dstep(rr)
    dl_db = layer.dl * EG_RANGE_DB / 32.0
    i = 0
    if att < 1.0 and a_step > 0:
        na = min(n_on, math.ceil((1.0 - att) / a_step))
        for k in range(na):
            env[k] = att + a_step * k
        att = min(1.0, att + a_step * na)
        i = na
    elif att < 1.0:
        return env
    if i < n_on:
        n = n_on - i
        n1 = (math.ceil(dl_db / s1) if dl_db > 0 else 0) if s1 > 0 else n
        n1 = min(n1, n)
        lvl = s1 * n1 if s1 > 0 else 0.0
        for k in range(n):
            c = s1 * k if k < n1 else lvl + s2 * (k - n1)
            c = min(c, EG_RANGE_DB)
            env[i + k] = att * math.pow(10, -c / 20.0)
        i = n_on
    if i < n_total:
        start = env[i - 1] if i > 0 else att
        start_db = -20 * math.log10(max(start, 1e-9))
        for k in range(n_total - i):
            if s_r > 0:
                c = min(start_db + s_r * (k + 1), EG_RANGE_DB)
                env[i + k] = 0.0 if c >= EG_RANGE_DB else math.pow(10, -c / 20.0)
            else:
                env[i + k] = start
    return env


def piecewise(points, default):
    pts = sorted(points, key=lambda p: (p[0], p[1]))

    def f(t):
        v = default
        for tm, x in pts:
            if t >= tm - 1e-12:
                v = x
        return v
    return f


def render_note(layer, sr, t_on, t_off, pitch, tail):
    i0 = round(t_on * sr)
    n_on = max(1, round((t_off - t_on) * sr))
    n_max = n_on + int(tail * sr)
    semis, pos, acc = [0.0] * n_max, [0.0] * n_max, 0
    for k in range(n_max):
        semis[k] = pitch(t_on + k / sr)
        pos[k] = acc
        acc += SCSP_RATE * math.pow(2.0, semis[k] / 12.0) / sr
    s = layer.samples
    n = len(s)
    length = n_max
    if layer.loop == 0:
        for k in range(n_max):
            if not pos[k] < n - 1 + 1e-9:
                length = k
                break
    else:
        ls = min(layer.lsa, n - 1)
        span = max(1, (n - 1) - ls)
        for k in range(n_max):
            if pos[k] > ls:
                if layer.loop in (1, 2):
                    pos[k] = ls + math.fmod(pos[k] - ls, span)
                else:
                    q = math.fmod(pos[k] - ls, 2 * span)
                    pos[k] = ls + (q if q < span else 2 * span - q)
    if length == 0:
        return i0, []
    out = [0.0] * length
    for k in range(length):
        ip = math.floor(pos[k])
        fr = pos[k] - ip
        a = s[min(max(ip, 0), n - 1)]
        b = s[min(max(ip + 1, 0), n - 1)]
        out[k] = a + (b - a) * fr
    ratio = SCSP_RATE * math.pow(2, semis[0] / 12.0) / SCSP_RATE
    octave = math.floor(math.log2(ratio))
    fns = int((ratio / math.pow(2, octave) - 1) * 1024)
    env = envelope(layer, min(n_on, length), length, sr, octave, (fns >> 9) & 1)
    return i0, [out[k] * env[k] for k in range(length)]


def render(ctx, sid, max_rate=SCSP_RATE, tail=2.0):
    """A Saturn sound id -> ([channels], rate, empty): floats, full scale 1.0, at the highest note
    playback rate (rounded up), at most max_rate."""
    c, off = ctx.locate(sid)
    if off is None:
        return [[]], SCSP_RATE, True
    seq = Seq(c.data, off)
    chan = [{"bank": 0, "prog": 0, "vol": [(0.0, 127)], "expr": [(0.0, 127)], "pan": [(0.0, 64)],
             "bend": [(0.0, 0x40)]} for _ in range(16)]
    notes = []
    for e in seq.events:
        st, ts = chan[e[2]], seq.seconds(e[0])
        if e[1] == "cc":
            num, val = e[3], e[4]
            if num == 32:
                st["bank"] = val
            elif num == 7:
                st["vol"].append((ts, val))
            elif num == 11:
                st["expr"].append((ts, val))
            elif num == 10:
                st["pan"].append((ts, val))
        elif e[1] == "prog":
            st["prog"] = e[3]
        elif e[1] == "bend":
            st["bend"].append((ts, e[3]))
        else:
            notes.append({"t": ts, "off": seq.seconds(e[0] + e[5]), "ch": e[2], "key": e[3], "vel": e[4],
                          "bank": st["bank"], "prog": st["prog"]})
    voices = []
    for n in notes:
        tb = ctx.tone_banks.get(n["bank"])
        if not tb or n["prog"] >= len(tb.voices):
            continue
        hdr, layers = tb.voices[n["prog"]]
        ly = next((lay for lay in layers if lay.lo <= n["key"] <= lay.hi), None)
        if ly is None:
            continue
        rng = hdr[0] & 0xF
        base = ly.base - ly.fine / 128.0
        bendf = piecewise(chan[n["ch"]]["bend"], 0x40)

        def pitch(t, key=n["key"], base=base, bendf=bendf, rng=rng):
            return key - base + (bendf(t) - 0x40) / 64.0 * rng
        voices.append((n, tb, ly, pitch, SCSP_RATE * math.pow(2, pitch(n["t"]) / 12.0)))
    if not voices:
        return [[]], SCSP_RATE, True
    rate = math.ceil(min(max_rate, SCSP_RATE, max(v[4] for v in voices)))
    stereo, rendered = False, []
    for n, tb, ly, pitch, _ in voices:
        i0, wav = render_note(ly, rate, n["t"], n["off"], pitch, tail)
        if not wav:
            continue
        st = chan[n["ch"]]
        vl = tb.vel_level(ly.vl_index, n["vel"])
        volf, exprf, panf = piecewise(st["vol"], 127), piecewise(st["expr"], 127), piecewise(st["pan"], 64)
        tl_gain = math.pow(10, -ly.tl * 0.375 / 20.0)
        disdl = 0.0 if ly.disdl == 0 else 2.0 ** (ly.disdl - 7)
        att = 1
        if ly.dipan & 0xF:
            att = math.pow(10, -3 * (ly.dipan & 0xF) / 20.0) if (ly.dipan & 0xF) != 0xF else 0.0
        w, lg, rg = [0.0] * len(wav), [0.0] * len(wav), [0.0] * len(wav)
        for k in range(len(wav)):
            t = n["t"] + k / rate
            vol, expr = volf(t), exprf(t)
            g = math.pow(10, -0.375 * ((127 - vl) + (127 - vol) + (127 - expr)) / 20.0)
            if vol <= 0:
                g = 0.0
            g = g * MIX_GAIN * tl_gain * disdl
            w[k] = wav[k] * g
            pan = panf(t)
            l_ = min(max((127 - pan) / 63.0, 0), 1)
            r_ = min(max(pan / 64.0, 0), 1)
            if ly.dipan & 0xF:
                if ly.dipan & 0x10:
                    r_ = r_ * att
                else:
                    l_ = l_ * att
            lg[k], rg[k] = l_, r_
            if abs(l_ - r_) > 1e-6:
                stereo = True
        rendered.append((i0, w, lg, rg))
    total = max(i0 + len(w) for i0, w, _, _ in rendered)
    L, R = [0.0] * total, [0.0] * total
    for i0, w, lg, rg in rendered:
        for k in range(len(w)):
            L[i0 + k] += w[k] * lg[k]
            R[i0 + k] += w[k] * rg[k]
    return ([L, R] if stereo else [L]), rate, False


def to_pcm16_mono(chans):
    """Trimmed (below -60 dBFS at the end), a stereo render averaged to mono, then 16-bit."""
    thr = math.pow(10, -60.0 / 20.0)
    last = -1
    for k in range(len(chans[0])):
        if max(abs(c[k]) for c in chans) > thr:
            last = k
    x = [c[:last + 1] for c in chans]
    m = [(v + x[1][k]) / 2 for k, v in enumerate(x[0])] if len(x) == 2 else x[0]
    peak = max((abs(v) for v in m), default=0)
    scale = (32767 / 32768) / peak if peak > 32767 / 32768 else 1.0
    return [min(32767, max(-32768, round(v * scale * 32768))) for v in m]

# ---------------------------------------------------------------- her banks (mar_sounds.ts)


VB_LEN = {1: 0xE190, 2: 0xFBF0}
VH_LEN = {1: 0x1020, 2: 0xE20}
TEMPLATE = {1: "VAB/SD_RIH", 2: "VAB/SD_MAR"}
VOX_TABLE = 0x0603A8B4 + 8
VOX_FIRST = 0x5CA
VOX_TRIM = 3
# (name, bank, PS1 id whose slot it fills, kind, source, class)
SOUNDS = [
    ("ATK_A", 1, 0x6F9, "seq", 0x71C, "voice"), ("ATK_B", 1, 0x6FA, "seq", 0x71D, "voice"),
    ("ATK_C", 1, 0x6FB, "seq", 0x71E, "voice"), ("KICK", 1, 0x6FC, "seq", 0x71F, "voice"),
    ("SHOT", 1, 0x6FD, "seq", 0x728, "sfx"), ("FIRE", 1, 0x6FE, "seq", 0x722, "sfx"),
    ("DEATH", 1, 0x6FF, "seq", 0x721, "voice"), ("BALL", 1, 0x700, "seq", 0x723, "sfx"),
    ("HURT_A", 1, 0x702, "vox", 0x5D4, "voice"), ("HURT_B", 1, 0x703, "vox", 0x5D6, "voice"),
    ("HURT_C", 1, 0x704, "vox", 0x5D7, "voice"), ("HIT", 1, 0x705, "ps1", 0x62E, "sfx"),
    ("LUNGE", 1, 0x6F4, "seq", 0x725, "buzz"), ("BEASTS_END", 1, 0x6F5, "seq", 0x727, "sfx"),
    ("GRAB_C", 1, 0x6F6, "vox", 0x5D8, "voice"), ("FLAP", 1, 0x6F7, "seq", 0x72E, "sfx"),
    ("SKID", 1, 0x707, "seq", 0x726, "sfx"),
    ("DIVE", 2, 0x87D, "vox", 0x5CA, "voice"), ("FOUR", 2, 0x87E, "vox", 0x5CE, "spell"),
    ("CUE", 2, 0x87F, "vox", 0x5CF, "voice"), ("SPELL", 2, 0x8A1, "vox", 0x5CC, "spell"),
    ("SPELL_1", 2, 0x8A2, "vox", 0x5D3, "spell"), ("SPELL_2", 2, 0x8A3, "vox", 0x5D2, "spell"),
    ("SPELL_3", 2, 0x8A4, "vox", 0x5D1, "spell"), ("SPELL_4", 2, 0x8A5, "vox", 0x5D0, "spell"),
    ("GRAB_B", 2, 0x880, "vox", 0x5D5, "voice"), ("GENBU", 2, 0x887, "seq", 0x72F, "long"),
    ("BYAKKO_FLAME", 2, 0x888, "seq", 0x72B, "sfx"), ("SEIRYU", 2, 0x889, "loop", 0x72C, "seiryu"),
    ("ROAR", 2, 0x88A, "roar", 0x72C, "roar"),
]
SEIRYU_RATE = 4912
LOOP_CUT = (0, 15756)
LOOP_START = 9156
LOOP_XFADE = 0.15
ROAR_CUT = (15122, 15122 + 10111)
ROAR_FADE = (0.010, 0.080)
FULL = {"sfx": 44100, "buzz": 44100, "long": 44100, "spell": 11025, "seiryu": 4912, "roar": 3500}
STEPS = ([dict(FULL, roar=r) for r in (3500, 3200, 3000, 2756, 2500)]
         + [dict(FULL, roar=2500, spell=n) for n in (10000, 9000, 8000)]
         + [dict(FULL, roar=2500, spell=8000, sfx=f, long=f) for f in (22050, 16000, 11025)]
         + [dict(FULL, roar=2500, spell=8000, sfx=11025, long=11025, buzz=b) for b in (22050, 14000)]
         + [dict(spell=n, seiryu=r, sfx=f, long=min(f, 5500), buzz=14000, roar=2205)
            for f, r, n in ((9000, 4000, 11025), (8000, 3300, 11025), (7000, 3300, 11025), (6000, 3300, 11025),
                            (6000, 2756, 10000), (6000, 2756, 9000), (5500, 2756, 8000))])
VOICE_PEAK = 29200
ADSR = (0x80FF, 0x5FC0)
SFX_TABLE = 0x1F554  # DRA.BIN: g_SfxData (0x800BF554), 7 bytes a sound from id 0x600


def sfx_config(dra):
    """{PS1 sound id: (vabid, prog, tone, note, volume)} from DRA's table."""
    out = {}
    for name, b, ps1, kind, src, _ in SOUNDS:
        for sid in ((ps1, src) if kind == "ps1" else (ps1,)):
            o = SFX_TABLE + (sid - 0x600) * 7
            vabid, prog, note, volume, _, tone = dra[o:o + 6]
            out[sid] = {"vabid": vabid, "prog": prog, "note": note, "volume": s8(volume), "tone": tone}
    return out


class Sources:
    def __init__(self, ctx, zero, sde7):
        self.ctx, self.zero, self.sde7 = ctx, zero, sde7
        self.cache, self.seiryu = {}, None

    def vox(self, sid):
        o = VOX_TABLE - ZERO_BASE + 12 * (sid - VOX_FIRST)
        off, ln = be32(self.zero, o), be32(self.zero, o + 4)
        rate = be16(self.zero, o + 8)
        if be16(self.zero, o + 10) != 1 or rate != 11025:
            raise ValueError(f"Saturn voice clip {sid:x}: unexpected format")
        s = [s8(b) for b in self.sde7[off:off + ln]]
        loud = [i for i, x in enumerate(s) if abs(x) > VOX_TRIM]
        return [x * 128 for x in s[loud[0]:loud[-1] + 1]], rate

    def seq(self, sid, cap):
        chans, rate, empty = render(self.ctx, sid, cap)
        if empty:
            raise ValueError(f"Saturn sound {sid:x}: empty")
        return to_pcm16_mono(chans), rate

    def seiryu_render(self):
        if self.seiryu is None:
            chans, rate, empty = render(self.ctx, 0x72C, SEIRYU_RATE)
            if empty or rate != SEIRYU_RATE:
                raise ValueError("Seiryuu: unexpected render")
            self.seiryu = to_pcm16_mono(chans)
        return self.seiryu

    def roar(self):
        x = [float(v) for v in self.seiryu_render()[ROAR_CUT[0]:ROAR_CUT[1]]]
        if len(x) != ROAR_CUT[1] - ROAR_CUT[0]:
            raise ValueError("Seiryuu: the render is too short for the roar")
        fin, fout = int(ROAR_FADE[0] * SEIRYU_RATE), int(ROAR_FADE[1] * SEIRYU_RATE)
        for k in range(fin):
            x[k] *= 0.5 - 0.5 * math.cos(math.pi * k / fin)
        for k in range(fout):
            x[len(x) - fout + k] *= 0.5 + 0.5 * math.cos(math.pi * (k + 1) / fout)
        return [round(v) for v in x], SEIRYU_RATE

    def loop(self):
        pcm = self.seiryu_render()[LOOP_CUT[0]:LOOP_CUT[1]]
        s, b = LOOP_START, 28
        end = s + (len(pcm) - s) // b * b
        x = [float(v) for v in pcm[:end]]
        c = int(LOOP_XFADE * SEIRYU_RATE) // b * b
        fade = np_linspace(0, 1, c)
        head, tail = x[end - c:end], x[s - c:s]
        for k in range(c):
            x[end - c + k] = head[k] * (1 - fade[k]) + tail[k] * fade[k]
        return [round(v) for v in x], SEIRYU_RATE

    def get(self, kind, src, cap):
        key = (kind, src, cap)
        if key not in self.cache:
            if kind == "loop":
                r = self.loop()
            elif kind == "seq":
                r = self.seq(src, cap)
            else:
                r = self.roar() if kind == "roar" else self.vox(src)
                if r[1] > cap:
                    r = resample(r[0], r[1], cap)
            self.cache[key] = r
        return self.cache[key]


def set_loop(v, start):
    """Loop flags on an encoded VAG: 6 at the loop start, 2 inside, 3 at the last block."""
    v = bytearray(v)
    n = len(v) // 16 - 2
    first = 1 + start // 28
    for k in range(1, n + 1):
        v[k * 16 + 1] = 0 if k < first else 6 if k == first else 2
    v[n * 16 + 1] = 3
    return bytes(v)


class Builder:
    def __init__(self, read_saturn, read_ps1, progress=None):
        self.ps1 = read_ps1
        self.cfg = sfx_config(read_ps1("DRA.BIN"))
        self.src = Sources(SfxContext(read_saturn), read_saturn("0.BIN"), read_saturn("SD/SDE7.PCM"))
        self.vags = {}  # (samples, rate) -> encoded: the same sound at the same cap, once
        self.progress = progress or (lambda f: None)

    def encode(self, pcm, rate):
        key = (tuple(pcm), rate)
        if key not in self.vags:
            self.vags[key] = vag(pcm)
        return self.vags[key]

    def bank(self, bank, caps):
        v = Vab(self.ps1(TEMPLATE[bank] + ".VH"), self.ps1(TEMPLATE[bank] + ".VB"))
        template = dict(v.tones[0][0])
        blank = next(t for tl in v.tones.values() for t in tl if t["vol"] == 0)
        for p in list(v.tones):
            v.tones[p] = [dict(blank, prog=p, vag=1) for _ in range(16)]
        silent = bytearray(48)
        silent[17], silent[33] = 1, 7
        silent[34:] = b"\x77" * 14
        v.vags = [bytes(silent)]

        def take(prog, tone):
            if v.tones[prog][tone]["vag"] != 1:
                raise ValueError(f"Maria vab {bank}: slot taken")
        for i, (name, b, ps1, kind, source, cls) in enumerate(SOUNDS):
            if b != bank:
                continue
            self.progress(i / len(SOUNDS))
            e = self.cfg[ps1]
            if e["vabid"] != bank:
                raise ValueError(name + ": sfx_config vab")
            take(e["prog"], e["tone"])
            if kind == "ps1":
                sv = Vab(self.ps1("SD_J010.VH"), self.ps1("SD_J010.VB"))
                o = self.cfg[source]
                st = sv.tones[o["prog"]][o["tone"]]
                v.vags.append(sv.vags[st["vag"] - 1])
                for k in (0, 1):  # the tone and its pair voice
                    t = sv.tones[o["prog"]][o["tone"] + k]
                    if k and (t["vag"] != st["vag"] or not t["vol"]):
                        break
                    take(e["prog"], e["tone"] + k)
                    v.tones[e["prog"]][e["tone"] + k] = dict(
                        t, prog=e["prog"], vag=len(v.vags), center=t["center"] + e["note"] - o["note"],
                        vol=min(127, round(t["vol"] * o["volume"] / e["volume"])))
                continue
            pcm, rate = self.src.get(kind, source, caps[cls])
            peak = max([1] + [abs(x) for x in pcm])
            gain = min(127.0 / e["volume"], 32000.0 / peak)
            if cls in ("voice", "spell"):
                gain = min(VOICE_PEAK / peak * 127.0 / e["volume"], 32000.0 / peak)
            out = [round(x * gain) for x in pcm] if gain > 1.0 else list(pcm)
            body = self.encode(out, rate)
            if kind == "loop":
                body = set_loop(body, LOOP_START)
            v.vags.append(body)
            c, f = centre(e["note"], rate)
            if not 0 <= c <= 127:
                raise ValueError(name + ": centre note out of range")
            v.tones[e["prog"]][e["tone"]] = dict(template, prog=e["prog"], vag=len(v.vags), vol=127, pan=64,
                                                 center=c, shift=f, min=0, max=127, adsr1=ADSR[0], adsr2=ADSR[1])
        return v


def finish(v, bank):
    """The VB padded to the size DRA transfers; None if it's over."""
    vh, vb = v.write()
    if len(vb) > VB_LEN[bank]:
        return None
    if len(vb) < VB_LEN[bank]:
        v.vags.append(bytes(VB_LEN[bank] - len(vb)))
        vh, vb = v.write()
    if len(vh) != VH_LEN[bank] or len(vb) != VB_LEN[bank]:
        raise ValueError(f"Maria vab {bank}: bank size")
    return vh, vb


def banks(read_saturn, read_ps1, progress=None):
    """(vh1, vb1, vh2, vb2): her two banks, each at the first rate caps it fits at."""
    b = Builder(read_saturn, read_ps1, progress)
    out = []
    for bank in (1, 2):
        classes = sorted({s[5] for s in SOUNDS if s[1] == bank} - {"voice"})
        tried, done = set(), None
        for step in STEPS:
            mine = tuple(step[c] for c in classes)
            if mine in tried:
                continue
            tried.add(mine)
            done = finish(b.bank(bank, dict(step, voice=44100)), bank)
            if done:
                break
        if not done:
            raise ValueError(f"Maria's vab {bank} doesn't fit at any rate cap")
        out += done
    return tuple(out)
