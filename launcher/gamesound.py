"""The game's title music and menu sounds, decoded from the player's PlayStation disc for the
launcher's menus (design/launcher-overhaul.md). Nothing here ships: the .wav files are made on
the player's machine, into their data folder.

    python launcher/gamesound.py <disc .cue or .bin> <out folder>

    rip(disc, out) -> True if every sound was made (sound.json lists them)
    ready(out)     -> True if out holds this version's sounds

Where they are (USA disc; docs/research.md "The game's art and sound"):
- Music is streamed: SD/XA_STR1 holds every track as CD-XA sound sectors, eight channels taking
  turns. DRA.BIN's table at 0x1D224 (16 bytes a track: sector, length, file, channel, volume)
  says where each starts. The title screen's is "Prayer", track 0x32; the row after a track is
  where it starts again from when it loops (Prayer: half way, 57.7 s in).
- A menu sound is a row of DRA.BIN's table at 0x1F554 (7 bytes: bank, program, note, volume,
  mode, tone). Bank 9 means a script instead: a list of (bank, program, note, tone, volume,
  frames) steps, found through the pointers at 0x21ECC. The samples are in SD_J010.VH / .VB,
  a standard PlayStation sound bank.
"""

import json
import mmap
import struct
import sys
import wave
from array import array
from pathlib import Path

HERE = Path(__file__).resolve().parent
for sub in ("patcher", ""):
    sys.path.insert(0, str(HERE.parent / sub) if sub else str(HERE.parent))

VERSION = 1  # of what rip() makes: a change here remakes every player's sounds
SECTOR = 2352
XA_TABLE, XA_ROW, PRAYER = 0x1D224, 16, 0x32
SFX_TABLE, SFX_ROW, SFX_SCRIPTS, DRA_BASE = 0x1F554, 7, 0x21ECC, 0x800A0000
SOUNDS = {"move": 0x67B, "confirm": 0x633, "back": 0x67D, "error": 0x686}  # the file select's own (src/st/sel)
RATE = 44100
XA_K = ((0, 0), (60, 0), (115, -52), (98, -55))
VAG_K = XA_K + ((122, -60),)
PIECES = ("music",) + tuple(SOUNDS)


# --- music: CD-XA

def xa_track(image, first, file, channel, limit=None):
    """A streamed track from a raw disc image: (rate, channels, samples as an array of 16-bit
    numbers). Reads the sectors of that file and channel from sector `first` until the stream
    says it's over (or `limit` of them)."""
    out = array("h")
    hist = [0, 0, 0, 0]  # left's last two samples, right's
    rate, stereo, n, at = 37800, True, 0, first
    signed = [v - 16 if v > 7 else v for v in range(16)]
    while (at + 1) * SECTOR <= len(image):
        s = image[at * SECTOR:(at + 1) * SECTOR]
        at += 1
        sfile, schannel, submode, coding = s[16], s[17], s[18], s[19]
        if not submode & 0x04 or sfile != file or schannel != channel:  # not sound, or another track's
            if n and at - first > 64 and not submode & 0x04 and sfile == file:
                break
            continue
        stereo, rate = bool(coding & 1), 18900 if coding & 4 else 37800
        for g in range(18):
            group = s[24 + g * 128:24 + (g + 1) * 128]
            units = []
            for u in range(8):
                shift, filt = group[4 + u] & 15, group[4 + u] >> 4 & 3
                k0, k1 = XA_K[filt]
                side = (u & 1) * 2 if stereo else 0
                p1, p2 = hist[side], hist[side + 1]
                low, base, block = u & 1, 16 + u // 2, []
                shift = 12 - shift if shift <= 12 else 3
                for i in range(28):
                    b = group[base + i * 4]
                    v = (signed[b >> 4 if low else b & 15] << shift) + ((p1 * k0 + p2 * k1 + 32) >> 6)
                    v = 32767 if v > 32767 else -32768 if v < -32768 else v
                    block.append(v)
                    p2, p1 = p1, v
                hist[side], hist[side + 1] = p1, p2
                units.append(block)
            if stereo:
                for u in range(0, 8, 2):
                    left, right = units[u], units[u + 1]
                    for i in range(28):
                        out.append(left[i])
                        out.append(right[i])
            else:
                for block in units:
                    out.extend(block)
        n += 1
        if submode & 0x80 or (limit and n >= limit):  # the stream's last sector
            break
    return rate, 2 if stereo else 1, out


def music(image, dra, track=PRAYER):
    from patcher import find_file
    place = find_file(image, "SD/XA_STR1.")
    if not place:
        return None
    sector, _length, file, channel = struct.unpack_from("<IIBB", dra, XA_TABLE + track * XA_ROW)
    again = struct.unpack_from("<I", dra, XA_TABLE + (track + 1) * XA_ROW)[0]  # the next row: where it loops from
    # the game adds the channel number to the sector it seeks to: the channels take turns
    rate, channels, samples = xa_track(image, place[0] + sector + channel, file, channel)
    loop = (again - sector) // 8 * 18 * 28 * 8 // 2 * channels if again > sector else 0  # 2016 stereo samples a sector
    return rate, channels, samples, loop if loop < len(samples) else 0


# --- menu sounds: a PlayStation sound bank (VAB) and the game's sound scripts

def vag(data):
    """One sample of a sound bank, decoded: an array of 16-bit numbers at 44.1 kHz."""
    out, p1, p2 = array("h"), 0, 0
    for at in range(0, len(data) - 15, 16):
        shift, filt, flags = data[at] & 15, data[at] >> 4, data[at + 1]
        if filt > 4:
            break
        k0, k1 = VAG_K[filt]
        shift = 12 - shift if shift <= 12 else 3
        for b in data[at + 2:at + 16]:
            for nib in (b & 15, b >> 4):
                v = ((nib - 16 if nib > 7 else nib) << shift) + ((p1 * k0 + p2 * k1 + 32) >> 6)
                v = 32767 if v > 32767 else -32768 if v < -32768 else v
                out.append(v)
                p2, p1 = p1, v
        if flags & 1:  # the sample's last block
            break
    return out


class Bank:
    """A sound bank: its header (.VH) and samples (.VB)."""

    def __init__(self, head, body):
        self.head, self.body = head, body
        programs, self.tones_total, vags = struct.unpack_from("<HHH", head, 0x12)
        self.used = [p for p in range(128) if head[0x20 + p * 16]]
        table = 0x820 + len(self.used) * 16 * 32
        sizes = [v << 3 for v in struct.unpack_from(f"<{vags + 1}H", head, table)]
        self.places, at = [], 0
        for size in sizes[1:]:  # (the table's first entry is empty: samples count from 1)
            self.places.append((at, size))
            at += size

    def tone(self, program, tone):
        """(volume, centre note, fine tune, sample number), or None."""
        if program not in self.used or tone >= self.head[0x20 + program * 16]:
            return None
        at = 0x820 + (self.used.index(program) * 16 + tone) * 32
        return self.head[at + 2], self.head[at + 4], self.head[at + 5], struct.unpack_from("<h", self.head, at + 22)[0]

    def note(self, program, tone, note, volume, frames=None):
        """That tone played at that note: floats at 44.1 kHz. frames: cut off after so many 60ths
        of a second (the next step of a script takes over), else to the sample's end."""
        t = self.tone(program, tone)
        if not t or not 1 <= t[3] <= len(self.places):
            return []
        tone_volume, centre, fine, sample = t
        at, size = self.places[sample - 1]
        pcm = vag(self.body[at:at + size])
        step = 2 ** ((note - centre) / 12 - fine / (128 * 12))
        length = int(len(pcm) / step)
        if frames is not None:
            length = min(length, frames * RATE // 60)
        gain = volume / 127 * tone_volume / 127 / 32768
        out = []
        for i in range(length):
            x = i * step
            k = int(x)
            a = pcm[k]
            b = pcm[k + 1] if k + 1 < len(pcm) else 0
            out.append((a + (b - a) * (x - k)) * gain)
        fade = min(len(out), RATE // 200)  # 5 ms: no click where it's cut
        for i in range(fade):
            out[-1 - i] *= i / fade
        return out


def sound(dra, bank, sfx):
    """A menu sound (its id, 0x600 up) as an array of 16-bit numbers, 44.1 kHz mono."""
    vab, program, note, volume, _mode, tone, _ = struct.unpack_from("<7B", dra, SFX_TABLE + (sfx - 0x600) * SFX_ROW)
    if vab != 9:
        mix = bank.note(program, tone, note, volume)
    else:  # a script: each step plays for its frames, then the next
        at = struct.unpack_from("<I", dra, SFX_SCRIPTS + (program + 1) * 4)[0] - DRA_BASE
        mix = []
        while 0 <= at < len(dra) - 6 and dra[at] != 0xFF and len(mix) < RATE * 4:
            _, s_program, s_note, s_tone, s_volume, frames = dra[at:at + 6]
            last = dra[at + 6] == 0xFF
            step = bank.note(s_program, s_tone, s_note, volume * s_volume // 127, None if last else frames)
            if not last:  # a sample that ends early leaves the rest of its frames silent
                step += [0.0] * (frames * RATE // 60 - len(step))
            mix += step
            at += 6
    return array("h", (max(-32768, min(32767, int(v * 32767))) for v in mix))


# --- files

def write_wav(path, rate, channels, samples):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(2)
        w.setframerate(rate)
        if sys.byteorder == "big":
            samples = array("h", samples)
            samples.byteswap()
        w.writeframes(samples.tobytes())


def ready(out):
    try:
        about = json.loads((Path(out) / "sound.json").read_text())
    except (OSError, ValueError):
        return False
    return about.get("version") == VERSION and all((Path(out) / f"{p}.wav").exists() for p in about.get("pieces", ()))


def rip(disc, out, progress=None):
    """Makes music.wav and the menu sounds in out. Returns True if every one was made. The music
    takes a while (it's a few minutes of sound, decoded in Python): run this off the menus' thread."""
    from gameart import disc_files
    from link import portraits
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    made = []
    try:
        files = disc_files(disc, ["DRA.BIN", "SD_J010.VH", "SD_J010.VB"])
        dra = files.get("DRA.BIN")
        if dra and "SD_J010.VH" in files and "SD_J010.VB" in files:
            bank = Bank(files["SD_J010.VH"], files["SD_J010.VB"])
            for name, sfx in SOUNDS.items():
                samples = sound(dra, bank, sfx)
                if len(samples) > RATE // 100:
                    write_wav(out / f"{name}.wav", RATE, 1, samples)
                    made.append(name)
        if dra:
            with open(portraits.track(disc), "rb") as f, mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as image:
                track = music(image, dra)
            if track and len(track[2]) > track[0]:
                rate, channels, samples, loop = track
                write_wav(out / "music.wav", rate, channels, samples)
                write_wav(out / "music_loop.wav", rate, channels, samples[loop:])  # what plays after the first time through
                made.append("music")
    except (OSError, ValueError, TypeError, AttributeError, struct.error, IndexError):
        pass
    (out / "sound.json").write_text(json.dumps({"version": VERSION, "pieces": sorted(made)}))
    return all(p in made for p in PIECES)


if __name__ == "__main__":
    print("all made" if rip(sys.argv[1], sys.argv[2]) else "some sounds are missing")
