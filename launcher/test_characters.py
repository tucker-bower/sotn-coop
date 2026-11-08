"""Maria from the player's own Dracula X Chronicles disc (design/M8 criteria 1 and 5).

    python launcher/test_characters.py

- test_pspus_extract: the USA DXC disc (disks/sotn.pspus.iso) and our patches make Maria's blob,
  and its overlay is exactly the one our build makes from the same disc (build/coop/maria);
- every wrong file gets a plain error that says what's needed: the European and Japanese PSP
  versions, a PlayStation disc, a random file;
- Maria's patches store nothing of the DXC disc's files (D71: every 64 bytes they store);
- test_saturn_maria (with the dev Saturn disc, LOCAL.md): Saturn Maria's blob from the Saturn disc
  and the co-op disc is exactly our build of her and of her partner, a PlayStation disc and a
  Saturn disc with one file changed are refused in words, and her patches store nothing of the
  Saturn files nor of the art made from them.
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


def fake_saturn_bin(path, files):
    """A tiny raw (2352-byte sector, mode 1) Saturn-style image holding these files."""
    def record(name, lba, size, is_dir=False):
        n = name.encode()
        r = bytearray(33 + len(n) + (1 - len(n) % 2))
        r[0] = len(r)
        struct.pack_into("<I", r, 2, lba)
        struct.pack_into("<I", r, 10, size)
        r[25] = 2 if is_dir else 0
        r[32] = len(n)
        r[33:33 + len(n)] = n
        return bytes(r)
    lba, root, data = 19, record("\0", 18, SECTOR, True) + record("\1", 18, SECTOR, True), []
    for name, b in files.items():
        root += record(name + ";1", lba, len(b))
        data.append((lba, b))
        lba += (len(b) + SECTOR - 1) // SECTOR
    iso = bytearray(SECTOR * lba)
    pvd = bytearray(SECTOR)
    pvd[0], pvd[1:6] = 1, b"CD001"
    pvd[156:156 + 34] = record("\0", 18, SECTOR, True)
    iso[16 * SECTOR:17 * SECTOR] = pvd
    iso[18 * SECTOR:18 * SECTOR + len(root)] = root
    for at, b in data:
        iso[at * SECTOR:at * SECTOR + len(b)] = b
    raw = bytearray()
    for k in range(lba):
        raw += bytes(15) + b"\x01" + iso[k * SECTOR:(k + 1) * SECTOR] + bytes(288)
    Path(path).write_bytes(raw)
    return path


def test_saturn_maria(tmp):
    """Saturn Maria (characters/maria-saturn): see the top. Skipped without the dev Saturn disc."""
    cue = next((DECOMP / "disks" / "saturn-disc").glob("*.cue"), None)
    coop = ROOT / ".env" / "out" / "disc" / "sotn_coop.us.cue"
    if not cue or not (PATCHES / "sat-maria.json").exists():
        print("-- test_saturn_maria: skipped (no dev Saturn disc or her patches)")
        return []
    out = []
    blob = characters.saturn_maria_blob(cue, coop, PATCHES, tmp / "sat.blob").read_bytes()
    magic, who, ovl, vh, vb, partner, vh2, vb2 = struct.unpack_from("<8I", blob)
    built = DECOMP / "build/coop/maria-saturn"
    al = lambda n: (n + 3) & ~3  # noqa: E731
    p0 = 32 + al(ovl) + al(vh) + al(vb)
    same = (who == characters.CHAR_SAT_MARIA and blob[32:32 + ovl] == (built / "SATMAR.BIN").read_bytes()
            and blob[p0:p0 + partner] == (built / "SATMARP.BIN").read_bytes())
    print(f"{'ok ' if same else 'BAD'} test_saturn_maria: her blob from the Saturn disc is our build "
          f"({ovl} bytes, and {partner} as the partner)")
    out.append(same)
    # her sound banks: the ones SOTN Ultimate makes, byte for byte (its MARIA_SD.BIN, when here)
    ult = Path("/home/tucker/research-src/sotn-ultimate/build/us/MARIA_SD.BIN")
    banks = (blob[32 + al(ovl):32 + al(ovl) + vh], blob[32 + al(ovl) + al(vh):32 + al(ovl) + al(vh) + vb],
             blob[p0 + al(partner):p0 + al(partner) + vh2], blob[p0 + al(partner) + al(vh2):p0 + al(partner) + al(vh2) + vb2])
    same = all(banks) and (not ult.exists() or [ult.read_bytes()[o:o + len(b)] for o, b in
                                                 zip((0, 3 * 2048, 32 * 2048, 34 * 2048), banks)] == list(banks))
    print(f"{'ok ' if same else 'BAD'} her two sound banks ({vh} + {vb}, {vh2} + {vb2} bytes)"
          f"{', identical to SOTN Ultimate' + chr(39) + 's' if ult.exists() else ''}")
    out.append(same)

    def refused(disc, words):
        try:
            characters.saturn_maria_blob(disc, coop, PATCHES, tmp / "x.blob")
        except characters.DiscError as e:
            ok = all(w in str(e) for w in words)
            print(f"{'ok ' if ok else 'BAD'} {Path(disc).name}: {e}")
            return ok
        print(f"BAD {Path(disc).name}: accepted")
        return False
    out.append(refused(coop, ["isn't the Saturn"]))
    # Ultimate Richter (D184): RIC.BIN with the coat, as SOTN Ultimate's build_ric2.py makes it
    ur = characters.ultimate_richter_blob(cue, coop, PATCHES, tmp / "ur.blob").read_bytes()
    who, size = struct.unpack_from("<2I", ur, 4)
    ult = Path("/home/tucker/research-src/sotn-ultimate/build/us/RIC2.BIN")
    same = who == characters.CHAR_ULT_RICHTER and ur[32:32 + 8] != b"" and (
        not ult.exists() or ur[32:32 + size] == ult.read_bytes()[:size])
    print(f"{'ok ' if same else 'BAD'} Ultimate Richter's blob: {size} bytes of RIC.BIN in the coat"
          f"{', identical to SOTN Ultimate' + chr(39) + 's RIC2.BIN' if ult.exists() else ''}")
    out.append(same)
    import json
    about = json.loads((PATCHES / "sat-maria.json").read_text())
    d = characters.RawDisc(characters.track1(cue))
    files = {n: d.read(n) for n in about["saturn_files"]}
    d.close()
    files["MAR_W.CHR"] = bytes(len(files["MAR_W.CHR"]))
    out.append(refused(fake_saturn_bin(tmp / "changed.bin", files), ["not the copy", "redump"]))
    # nothing of the Saturn's in her patches: neither its files nor the art made from them
    sys.path.insert(0, str(ROOT / "patcher"))
    from test_patcher import stored
    d = characters.RawDisc(characters.track1(cue))
    files = {n: d.read(n) for n in about["saturn_files"]}
    d.close()
    made = blob[32:32 + ovl]
    chunks = set()
    for data in list(files.values()) + [made[at:at + size] for at, size, _ in about["arrays"].values()]:
        chunks.update(data[k:k + 32] for k in range(0, len(data) - 31, 4))
    found = total = 0
    for name in ("sat-maria.bps", "sat-maria-partner.bps"):
        for _, data in stored((PATCHES / name).read_bytes()):
            total += len(data)
            found += sum(1 for k in range(0, len(data) - 31, 4)
                         if len(set(data[k:k + 32])) > 4 and data[k:k + 32] in chunks)
    print(f"{'ok ' if not found else 'BAD'} Saturn Maria's patches store {total} bytes of ours, "
          f"{found} pieces of the Saturn's")
    out.append(not found)
    return out


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
    for name in ("maria.bps", "maria-vh.bps", "maria-vb.bps", "maria-partner.bps"):
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
        results += test_saturn_maria(tmp)
    print("PASSED" if all(results) else "FAILED")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
