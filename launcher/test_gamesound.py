"""The game's music and menu sounds for the menus (launcher/gamesound.py), on made-up files: no game
data is needed, and none is made. With a dev checkout's disc (COOP_TEST_DISC, or
disks/sotn.us.cue) it also decodes the real ones into a temporary folder.

    python launcher/test_gamesound.py
"""

import math
import os
import struct
import sys
import tempfile
import wave
from array import array
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

import gamesound  # noqa: E402

failures = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def xa_sector(file, channel, nibble, last=False, sound=True):
    """A CD-XA sector whose every sample is `nibble` << 12 (filter 0, no shift), in stereo."""
    s = bytearray(gamesound.SECTOR)
    s[16:20] = bytes((file, channel, (0x04 if sound else 0x08) | (0x80 if last else 0), 0x01))
    for g in range(18):
        at = 24 + g * 128
        s[at + 16:at + 128] = bytes([nibble | nibble << 4]) * 112
    return bytes(s)


def made_up_bank(pcm):
    """A sound bank with one program (5) of three tones, all the same sample, centred on note 60."""
    from saturn_maria_sounds import vag
    body = vag(pcm)
    head = bytearray(0x820 + 16 * 32 + 512)
    head[0:4] = b"pBAV"
    struct.pack_into("<HHH", head, 0x12, 1, 3, 1)
    head[0x20 + 5 * 16] = 3
    for tone in range(3):
        at = 0x820 + tone * 32
        head[at + 2], head[at + 4], head[at + 5] = 127, 60, 0
        struct.pack_into("<h", head, at + 22, 1)
    struct.pack_into("<2H", head, 0x820 + 16 * 32, 0, len(body) >> 3)
    return gamesound.Bank(bytes(head), body)


def made_up_dra():
    """The game's sound tables: sound 0x601 plays program 5's tone 2; sound 0x602 is script 0,
    two steps of 3 and 2 frames and a last one."""
    dra = bytearray(0x22000)
    dra[gamesound.SFX_TABLE + 7:gamesound.SFX_TABLE + 14] = bytes((0, 5, 60, 127, 0, 2, 30))
    dra[gamesound.SFX_TABLE + 14:gamesound.SFX_TABLE + 21] = bytes((9, 0, 0, 127, 0, 0, 30))
    script = 0x20000
    struct.pack_into("<I", dra, gamesound.SFX_SCRIPTS + 4, gamesound.DRA_BASE + script)
    dra[script:script + 19] = bytes((0, 5, 72, 0, 127, 3)) + bytes((0, 5, 60, 0, 64, 2)) + bytes((0, 5, 60, 1, 127, 1)) + b"\xff"
    return bytes(dra)


def main():
    # CD-XA: two tracks taking turns in one file
    image = (xa_sector(1, 4, 3) + xa_sector(1, 5, 7) + xa_sector(1, 4, 0xF, sound=False) + xa_sector(1, 4, 0xE, last=True)
             + xa_sector(1, 4, 1))
    rate, channels, samples = gamesound.xa_track(image, 0, 1, 4)
    per = 18 * 8 * 28
    check((rate, channels, len(samples)) == (37800, 2, per * 2), f"an XA track: its own sound sectors, up to its last ({len(samples)} samples)")
    check(set(samples[:per]) == {3 << 12} and set(samples[per:]) == {-2 << 12},
          "an XA track: the samples are the sectors', the other channel's and the data sector's left out")
    check(len(gamesound.xa_track(image[:100], 0, 1, 4)[2]) == 0 and len(gamesound.xa_track(image, 0, 9, 9)[2]) == 0,
          "an image cut short, or a track that isn't there: no samples, nothing raises")

    # a sound bank's sample, there and back
    pcm = [int(12000 * math.sin(i * 2 * math.pi * 441 / 44100)) for i in range(2800)]
    from saturn_maria_sounds import vag
    back = gamesound.vag(vag(pcm))[28:]  # (the encoder leads with an empty block)
    error = math.sqrt(sum((a - b) ** 2 for a, b in zip(pcm, back)) / len(pcm))
    check(len(back) >= len(pcm) and error < 400, f"a bank's sample decodes to what was encoded (error {error:.0f} of 12000)")

    bank, dra = made_up_bank(pcm), made_up_dra()
    plain = gamesound.sound(dra, bank, 0x601)
    check(abs(len(plain) - 2828) <= 56 and max(plain) > 10000, f"a plain sound: the tone at its own note ({len(plain)} samples)")
    high = bank.note(5, 0, 72, 127)
    check(abs(len(high) - 2828 // 2) <= 28, f"an octave up: half as long ({len(high)} samples)")
    check(bank.note(9, 0, 60, 127) == [] and bank.note(5, 7, 60, 127) == [], "a program or tone the bank hasn't: silence")
    script = gamesound.sound(dra, bank, 0x602)
    steps = 3 * 735 + 2 * 735
    check(abs(len(script) - (steps + 2828)) <= 56, f"a script: each step for its frames, the last to its end ({len(script)} samples)")
    loud = max(abs(v) for v in script[100:2000])
    quiet = max(abs(v) for v in script[3 * 735 + 100:5 * 735 - 100])
    check(quiet < loud * 0.6, f"a script: each step at its own volume ({loud}, then {quiet})")

    with tempfile.TemporaryDirectory() as d:
        ok = gamesound.rip(Path(d) / "no-such-disc.cue", Path(d) / "sound")
        check(ok is False and gamesound.ready(Path(d) / "sound") and not gamesound.ready(d),
              "a disc that can't be read: rip says sounds are missing, and isn't asked again for this version")

    disc = os.environ.get("COOP_TEST_DISC") or HERE.parent / "disks" / "sotn.us.cue"
    if Path(disc).exists():
        with tempfile.TemporaryDirectory() as d:  # (game data: gone when the test ends)
            check(gamesound.rip(disc, d) and gamesound.ready(d), "the real disc: the music and every menu sound are made")
            with wave.open(str(Path(d) / "music.wav")) as w:
                seconds = w.getnframes() / w.getframerate()
                a = array("h", w.readframes(w.getnframes()))[::2]
            with wave.open(str(Path(d) / "music_loop.wav")) as w:
                loop = w.getnframes() / w.getframerate()
            a = a[len(a) // 4:len(a) // 4 + 100000]
            rms = math.sqrt(sum(x * x for x in a) / len(a))
            jump = math.sqrt(sum((a[i + 1] - a[i]) ** 2 for i in range(len(a) - 1)) / len(a))
            check(100 < seconds < 130 and 50 < loop < 65, f"the real disc: the music is {seconds:.0f} s, and loops over its last {loop:.0f} s")
            check(rms > 500 and jump / rms < 0.5, f"the real disc: the music is sound, not noise (noise is 1.41: {jump / rms:.2f})")
            for name in gamesound.SOUNDS:
                with wave.open(str(Path(d) / f"{name}.wav")) as w:
                    n = w.getnframes() / w.getframerate()
                check(0.05 < n < 1.5, f"the real disc: the {name} sound is {n:.2f} s")
    else:
        print("     (no disc here: the real sounds aren't checked)")

    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
