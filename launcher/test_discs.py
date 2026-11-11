"""Which disc a file is (launcher/discs.py), on made-up files: a few bytes shaped like each
system's disc. With a dev checkout's discs it also checks the real ones. No game data is made.

    python launcher/test_discs.py
"""

import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

import discs  # noqa: E402

failures = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def raw_cd(system):
    """Seventeen raw sectors, the last a volume descriptor naming the system."""
    out = bytearray(17 * 2352)
    for n in range(17):
        out[n * 2352:n * 2352 + 12] = discs.RAW_SYNC
    out[16 * 2352 + 24:16 * 2352 + 30] = b"\x01CD001"
    out[16 * 2352 + 32:16 * 2352 + 32 + len(system)] = system
    return bytes(out)


def iso(system):
    out = bytearray(0x8800)
    out[0x8000:0x8006] = b"\x01CD001"
    out[0x8008:0x8008 + len(system)] = system
    return bytes(out)


def main():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "sotn.bin").write_bytes(raw_cd(b"PLAYSTATION"))
        (d / "sotn.cue").write_text('FILE "sotn.bin" BINARY\n  TRACK 01 MODE2/2352\n    INDEX 01 00:00:00\n')
        (d / "dxc.iso").write_bytes(iso(b"PSP GAME"))
        saturn = bytearray(raw_cd(b""))
        saturn[16:31] = b"SEGA SEGASATURN"
        (d / "saturn.bin").write_bytes(bytes(saturn))
        (d / "saturn.cue").write_text('FILE "saturn.bin" BINARY\n  TRACK 01 MODE1/2352\n')
        (d / "saturn-plain.bin").write_bytes(b"SEGA SEGASATURN " + bytes(4000))
        (d / "music.bin").write_bytes(raw_cd(b"CD-RTOS"))
        (d / "notes.txt").write_text("hello")
        (d / "lost.cue").write_text('FILE "gone.bin" BINARY\n')
        (d / "empty.cue").write_text("")
        check(discs.kind(d / "sotn.cue") == "ps1" and discs.kind(d / "sotn.bin") == "ps1", "a PlayStation disc, by its .cue or its .bin")
        check(discs.kind(d / "dxc.iso") == "psp", "a PSP disc image")
        check(discs.kind(d / "saturn.cue") == "saturn" and discs.kind(d / "saturn-plain.bin") == "saturn",
              "a Saturn disc, as raw sectors or plain ones")
        (d / "renamed.iso").write_bytes(raw_cd(b"PLAYSTATION"))
        check(discs.kind(d / "renamed.iso") == "ps1", "it goes by what's in the file, not its name")
        check([discs.kind(d / n) for n in ("music.bin", "notes.txt", "lost.cue", "empty.cue", "no-such-file.cue")] == [None] * 5,
              "another kind of CD, a text file, a .cue whose file is gone, an empty .cue, no file: none of them, and nothing raises")

    real = HERE.parent / "disks"
    found = [(real / "sotn.us.cue", "ps1"), (real / "sotn.pspus.iso", "psp")] + [(p, "saturn") for p in sorted((real / "saturn-disc").glob("*.cue"))[:1]]
    for path, want in found:
        if path.exists():
            check(discs.kind(path) == want, f"the real {want} disc is one ({path.name})")
    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
