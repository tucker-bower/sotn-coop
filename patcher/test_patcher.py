"""Patcher checks (M6 criterion 2): run after scripts/build_disc.sh.

    python patcher/test_patcher.py

- the patch made from the retail disc and our build turns the retail disc into our build,
  byte for byte, and copies the audio track as it is;
- the player's disc is never changed;
- a modified rip, and something that isn't a PlayStation disc, are refused in plain words.
Everything is written to a temporary folder (game data: never commit it)."""

import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import patcher  # noqa: E402

ROOT = HERE.parents[2]
RETAIL_CUE = ROOT / "disks/sotn.us.cue"
BUILT = HERE.parent / ".env/out/disc/sotn_coop.us.bin"


def digest(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    tracks = patcher.parse_cue(RETAIL_CUE)
    track1, track2 = tracks[0][0], tracks[1][0]
    before = digest(track1)
    with tempfile.TemporaryDirectory(prefix="coop-patcher-") as tmp:
        tmp = Path(tmp)
        patch = patcher.make(track1, BUILT, tmp / "dist", "test")
        size = patch.stat().st_size
        assert size < 1 << 20, f"the patch is {size} bytes: it should hold only our changes"
        cue = patcher.apply(RETAIL_CUE, patch, tmp / "out")
        made = patcher.parse_cue(cue)
        assert digest(made[0][0]) == digest(BUILT), "the patched disc isn't our build"
        assert digest(made[1][0]) == digest(track2), "the audio track changed"
        assert digest(track1) == before, "the player's disc was changed"
        print(f"ok: patch {size} bytes; patched disc = build; audio track kept; original untouched")

        bad = tmp / "modified.bin"
        shutil.copyfile(track1, bad)
        with open(bad, "r+b") as f:
            f.seek(100_000_000)
            byte = f.read(1)
            f.seek(100_000_000)
            f.write(bytes([byte[0] ^ 0xFF]))
        try:
            patcher.apply(bad, patch, tmp / "bad")
            raise AssertionError("a modified rip was accepted")
        except patcher.DiscError as e:
            assert "not an exact copy" in str(e), e
            print("ok: modified rip refused:", e)

        junk = tmp / "notadisc.bin"
        junk.write_bytes(b"\0" * 10_000_000)
        try:
            patcher.apply(junk, patch, tmp / "junk")
            raise AssertionError("a non-disc was accepted")
        except patcher.DiscError as e:
            assert "PlayStation" in str(e), e
            print("ok: non-disc refused:", e)


if __name__ == "__main__":
    main()
