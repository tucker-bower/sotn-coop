"""Maria from the player's own Dracula X Chronicles disc (design/M8 criteria 1 and 5).

    python launcher/test_characters.py

- test_pspus_extract: the USA DXC disc (disks/sotn.pspus.iso) and our patches make Maria's blob,
  and its overlay is exactly the one our build makes from the same disc (build/coop/maria);
- every wrong file gets a plain error that says what's needed: the European and Japanese PSP
  versions, a PlayStation disc, a random file;
- Maria's patches store nothing of the DXC disc's files (D71: every 64 bytes they store).
Everything is written to a temporary folder (game data: never commit it)."""

import struct
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
import characters  # noqa: E402

DXC = ROOT / "disks" / "sotn.pspus.iso"
PATCHES = ROOT / ".env" / "out" / "maria"
DECOMP = ROOT / ".env" / "src" / "sotn-decomp"
SECTOR = 2048


def fake_psp_iso(path, game_id):
    """A tiny ISO 9660 image holding only UMD_DATA.BIN (what check_dxc reads), for game_id."""
    umd = f"{game_id}|0000000000000001|0001|G".encode()

    def record(name, lba, size, is_dir=False):
        n = name.encode()
        r = bytearray(33 + len(n) + (1 - len(n) % 2))
        r[0] = len(r)
        struct.pack_into("<I", r, 2, lba)
        struct.pack_into(">I", r, 6, lba)
        struct.pack_into("<I", r, 10, size)
        struct.pack_into(">I", r, 14, size)
        r[25] = 2 if is_dir else 0
        r[32] = len(n)
        r[33:33 + len(n)] = n
        return bytes(r)

    root = record("\0", 18, SECTOR, True) + record("\1", 18, SECTOR, True) + record("UMD_DATA.BIN;1", 19, len(umd))
    pvd = bytearray(SECTOR)
    pvd[0], pvd[1:6], pvd[6] = 1, b"CD001", 1
    pvd[156:156 + 34] = record("\0", 18, SECTOR, True)
    img = bytearray(SECTOR * 20)
    img[16 * SECTOR:17 * SECTOR] = pvd
    img[17 * SECTOR] = 255  # terminator
    img[17 * SECTOR + 1:17 * SECTOR + 6] = b"CD001"
    img[18 * SECTOR:18 * SECTOR + len(root)] = root
    img[19 * SECTOR:19 * SECTOR + len(umd)] = umd
    Path(path).write_bytes(img)
    return path


def expect_error(path, words):
    try:
        characters.maria_blob(path, PATCHES, Path(path).with_suffix(".blob"))
    except characters.DiscError as e:
        ok = all(w in str(e) for w in words)
        print(f"{'ok ' if ok else 'BAD'} {Path(path).name}: {e}")
        return ok
    print(f"BAD {Path(path).name}: accepted")
    return False


def no_disc_data():
    sys.path.insert(0, str(ROOT / "patcher"))
    from test_patcher import stored
    iso = characters.Iso(DXC)
    files = {name: iso.read(path) for name, path in characters.FILES.items()}
    iso.close()
    chunks = set()
    for data in files.values():
        chunks.update(data[k:k + 64] for k in range(0, len(data) - 63, 4))
    found = total = 0
    for name in ("maria.bps", "maria-vh.bps", "maria-vb.bps"):
        for _, data in stored((PATCHES / name).read_bytes()):
            total += len(data)
            found += sum(1 for k in range(0, len(data) - 63, 16)
                         if len(set(data[k:k + 64])) > 4 and data[k:k + 64] in chunks)
    print(f"{'ok ' if not found else 'BAD'} Maria's patches store {total} bytes of ours, "
          f"{found} pieces of the DXC disc's files")
    return not found


def main():
    results = []
    with tempfile.TemporaryDirectory(prefix="coop-characters-") as tmp:
        tmp = Path(tmp)
        blob = characters.maria_blob(DXC, PATCHES, tmp / "maria.blob").read_bytes()
        magic, who, ovl, vh, vb = struct.unpack_from("<5I", blob)
        built = (DECOMP / "build/coop/maria/MARIA.BIN").read_bytes()
        same = magic == characters.CHAR_BLOB_MAGIC and who == characters.CHAR_MARIA and \
            blob[32:32 + ovl] == built and vh > 0 and vb > 0
        print(f"{'ok ' if same else 'BAD'} test_pspus_extract: Maria's blob from the USA DXC disc "
              f"({ovl} bytes of overlay, identical to our build; voice {vh} + {vb} bytes)")
        results.append(same)
        results.append(expect_error(fake_psp_iso(tmp / "eu.iso", "ULES-00841"), ["European", "ULUS-10277"]))
        results.append(expect_error(fake_psp_iso(tmp / "jp.iso", "ULJM-05201"), ["Japanese", "ULUS-10277"]))
        results.append(expect_error(fake_psp_iso(tmp / "other.iso", "ULUS-10000"), ["Dracula X Chronicles", "ULUS-10277"]))
        sotn = next((ROOT / "disks").glob("*Track 1).bin"), None) or next((ROOT / "disks").glob("*.bin"))
        results.append(expect_error(sotn, ["PlayStation disc", "Dracula X Chronicles"]))
        junk = tmp / "notes.txt"
        junk.write_bytes(b"hello" * 2000)
        results.append(expect_error(junk, ["isn't a disc image"]))
        results.append(no_disc_data())
    print("PASSED" if all(results) else "FAILED")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
