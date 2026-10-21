"""Patcher checks (M6 criterion 2): run after scripts/build_disc.sh.

    python patcher/test_patcher.py

- the patch made from the retail disc and our build turns the retail disc into our build,
  byte for byte, and copies the audio track as it is;
- the player's disc is never changed;
- a modified rip, and something that isn't a PlayStation disc, are refused in plain words;
- the patch stores no game data (D71): no sector checksums, and nothing of the retail files
  (every 64 bytes it stores, checked against every retail data sector; the disc's directory,
  which lists our files too, and compiler idioms up to 32 bytes long do match by nature).
Everything is written to a temporary folder (game data: never commit it)."""

import hashlib
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "harness"))
from coop_env import DISKS  # noqa: E402
import patcher  # noqa: E402

RETAIL_CUE = DISKS / "sotn.us.cue"
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
        shutil.rmtree(tmp / "out")
        print(f"ok: patch {size} bytes; patched disc = build; audio track kept; original untouched")
        check_no_game_data(patch.read_bytes(), track1)

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


def stored(patch):
    """[(target offset, bytes)] of everything the patch stores (TARGET_READ)."""
    bps = patcher.bps
    _, pos = bps._read_number(patch, 4)
    _, pos = bps._read_number(patch, pos)
    n, pos = bps._read_number(patch, pos)
    pos += n
    out, o = [], 0
    while pos < len(patch) - 12:
        word, pos = bps._read_number(patch, pos)
        action, length = word & 3, (word >> 2) + 1
        if action == bps.TARGET_READ:
            out.append((o, patch[pos:pos + length]))
            pos += length
        elif action in (bps.SOURCE_COPY, bps.TARGET_COPY):
            _, pos = bps._read_number(patch, pos)
        o += length
    return out


def check_no_game_data(patch, track1):
    retail = Path(track1).read_bytes()
    S = patcher.SECTOR
    chunks = set()
    for i in range(0, len(retail) - S + 1, S):
        data = retail[i + 24:i + 24 + 2048]
        if retail[i + 15] == 2 and not retail[i + 18] & 0x20:  # form 1 data
            chunks.update(data[k:k + 64] for k in range(0, 2048 - 63, 4))
    built = BUILT.read_bytes()
    form1 = lambda i: built[i * S + 15] == 2 and not built[i * S + 18] & 0x20  # noqa: E731
    found = ecc = 0
    for o, data in stored(patch):
        for k in range(0, len(data) - 63, 16):
            c = data[k:k + 64]
            if (o + k) // S >= 32 and len(set(c)) > 4 and c in chunks:  # past the volume and its directory
                found += 1
        for k in range(len(data)):  # a stored byte inside a form 1 sector's EDC/ECC (0x818-0x930)
            if (o + k) % S >= 0x818 and data[k] and form1((o + k) // S):
                ecc += 1
                break
    assert not ecc, f"the patch stores sector checksums ({ecc} runs)"
    assert not found, f"the patch stores {found} pieces of retail data"
    print("ok: the patch stores no sector checksums and nothing of the retail disc's data")


if __name__ == "__main__":
    main()
