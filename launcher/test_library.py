"""Game discs (launcher/library.py) without making any: names, how each stands with co-op, removal,
the old randomizer setting becoming a game disc, and the Alternate Scarlet Symphony download (a
fake server: the right file, a wrong one, none). No game data is needed.

    python launcher/test_library.py
"""

import hashlib
import io
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent), str(HERE.parent / "patcher")]

failures = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


class Reply(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def main():
    with tempfile.TemporaryDirectory() as d:
        os.environ["COOP_DATA"] = d
        import library
        info = {"seed": "abc", "version": "26.07.13", "preset": "casual"}
        st = {}
        seed = {"kind": "randomizer", "file": "seed-1.sdif", "info": info}
        hacks = {"kind": "hacks", "ids": ["minimap", "fast-warp"]}
        check(library.describe(None) is None and library.name(None) == library.PLAIN and library.current(st) is None,
              "nothing in use: Co-op (no mods), described as None (what partners compare)")
        a = library.add(st, [seed, hacks])
        b = library.add(st, [dict(hacks, ids=["fast-warp", "minimap"]), seed])
        check(library.describe(a) == library.describe(b) and "seed abc" in library.describe(a) and "Fast Warp, MiniMap" in library.describe(a),
              f"the same mods are described the same whatever their order: {library.describe(a)!r}")
        check(library.name(a) == "Casual abc + Fast Warp and 1 more", f"its short name: {library.name(a)!r}")
        a["name"] = "Our run"
        check(library.name(a) == "Our run" and library.describe(a) != "Our run", "a name the player gives it shows; partners still compare what's in it")
        check([library.standing({"mods": [seed]}), library.standing({"mods": [hacks]}), library.standing(a),
               library.standing({"mods": [{"kind": "ppf", "file": "x.ppf", "crc": 1}]})] ==
              ["", "", "each part tested alone", "untested with co-op"], "how each stands: tested, a combination, an unknown patch")
        mods = library.folder() / "mods"
        (mods / "seed-1.sdif").write_bytes(b"x")
        st["game_disc"] = a["id"]
        library.remove(st, a["id"])
        check(library.get(st, a["id"]) is None and st["game_disc"] is None and (mods / "seed-1.sdif").exists(),
              "removing one in use: Co-op (no mods) is in use, and a file another disc uses stays")
        library.remove(st, b["id"])
        check(not (mods / "seed-1.sdif").exists() and library.discs(st) == [], "removing the last one to use it: the file goes")

        # The randomizer setting from before game discs
        ppf = Path(d) / "seed.ppf"
        ppf.write_bytes(b"PPF30 made up")
        old = {"randomizer": {"cue": str(Path(d) / "gone.cue"), "source": str(ppf), "info": info, "crc": 5, "on": True, "patch": 7}}
        check(library.migrate(old) and "randomizer" not in old and library.current(old)["mods"][0]["kind"] == "randomizer"
              and (mods / library.current(old)["mods"][0]["file"]).exists(),
              "the old randomizer setting becomes a game disc, in use as it was on, its .ppf kept")
        check(not library.migrate(old), "and only once")

        # Alternate Scarlet Symphony
        right = b"ass" * 10
        library.ASS.update(sha256=hashlib.sha256(right).hexdigest(), size=len(right))
        try:
            library.download_ass(opener=lambda req, timeout: Reply(b"not it"))
            check(False, "a download that isn't the tested file is refused")
        except OSError as e:
            check("checksum" in str(e) and not library.have_ass(), f"a download that isn't the tested file is refused, and not kept: {e}")

        def offline(req, timeout):
            raise OSError("no network")
        try:
            library.download_ass(opener=offline)
            check(False, "no internet: says so")
        except OSError as e:
            check("internet" in str(e), f"no internet: says so ({e})")
        seen = []
        path = library.download_ass(progress=lambda got, of: seen.append((got, of)), opener=lambda req, timeout: Reply(right))
        check(path.read_bytes() == right and library.have_ass() and seen[-1] == (len(right), len(right)),
              "the tested file: downloaded, checked, kept, with progress")
        check(library.download_ass(opener=offline) == path, "once it's here it isn't downloaded again")
        other = Path(d) / "ASS-F.01.ppf"
        other.write_bytes(right)
        library.ass_path().unlink()
        check(library.keep_ass_file(other) and library.have_ass(), "the player's own copy of the tested file is taken too")
        other.write_bytes(b"something else")
        check(not library.keep_ass_file(other), "but not another file")
        # With a dev checkout's discs: images are made, and only the KEEP_IMAGES used last are kept
        disks = HERE.parent / "disks"
        retail, coop = disks / "sotn.us.cue", disks / "sotn.us (Co-op).cue"
        if retail.exists() and coop.exists():
            sys.path.insert(0, str(HERE.parent / "scripts"))
            import disk_space
            disk_space.check()
            import shutil
            import time
            # (images are 540 MB: never in /tmp, which is memory; next to the discs' own filesystem)
            work = HERE.parent / ".env" / "out" / "test-library"
            shutil.rmtree(work, ignore_errors=True)
            work.mkdir(parents=True)
            os.environ["COOP_DATA"] = str(work)
            st = {}
            made = []
            for hid in ("fast-warp", "slogra", "karasuman", "wolf-no-jump"):
                g = library.add(st, [{"kind": "hacks", "ids": [hid]}])
                t0 = time.time()
                cue = library.build(st, g, retail, coop, 1)
                made.append((g, cue, time.time() - t0))
            kept = [g for g, *_ in made if library.ready(g, 1)]
            check([g["id"] for g in kept] == [g["id"] for g, *_ in made[1:]] and not (library.folder() / made[0][0]["id"]).exists(),
                  f"four game discs made ({', '.join(f'{t:.0f} s' for *_, t in made)}): the three used last keep their image")
            track2 = Path(made[-1][1]).with_name("Symphony of the Night (Co-op, modded) (Track 2).bin")
            check(track2.exists() and track2.stat().st_nlink > 1, "the audio track is linked to the co-op disc's, not copied")
            check(not library.ready(made[-1][0], 2), "after an update (another co-op patch) it's made again")
            for g, *_ in made:
                library.remove(st, g["id"])
            check(not any(p.suffix == ".bin" for p in library.folder().rglob("*")), "removed: no image is left")
            shutil.rmtree(work, ignore_errors=True)
        else:
            print("     (no discs here: making images isn't checked)")
    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
