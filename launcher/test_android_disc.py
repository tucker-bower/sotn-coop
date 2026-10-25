"""Android's disc setup (design/M9 criterion 4): the player picks the folder their disc is in.

    python launcher/test_android_disc.py

- disc_files picks the SOTN .cue and the files it names, whatever the folder holds (other
  games' rips, a .cue whose .bin is missing, names in another case: saved as the .cue names
  them, a rip in a folder inside the one picked), else a lone .bin, else a .zip;
- unzip_disc unpacks a .zip of a rip and gives back its .cue.
No game data: the files are tiny fakes in a temporary folder."""

import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "patcher"))
from platform_android import disc_files, unzip_disc  # noqa: E402

SOTN = "Castlevania - Symphony of the Night (USA)"
CUE = f'FILE "{SOTN} (Track 1).bin" BINARY\n  TRACK 01 MODE2/2352\n' \
      f'FILE "{SOTN} (Track 2).bin" BINARY\n  TRACK 02 AUDIO\n'
FOLDERS = {
    "a redump rip": ({f"{SOTN}.cue": CUE, f"{SOTN} (Track 1).bin": "", f"{SOTN} (Track 2).bin": ""},
                     [(n, n) for n in (f"{SOTN}.cue", f"{SOTN} (Track 1).bin", f"{SOTN} (Track 2).bin")]),
    "next to another game's rip": (
        {"Metal Gear Solid.cue": 'FILE "mgs.bin" BINARY\n  TRACK 01 MODE2/2352\n', "mgs.bin": "",
         f"{SOTN}.cue": CUE, f"{SOTN} (Track 1).bin": "", f"{SOTN} (Track 2).bin": "", "notes.txt": ""},
        [(n, n) for n in (f"{SOTN}.cue", f"{SOTN} (Track 1).bin", f"{SOTN} (Track 2).bin")]),
    "names in another case": ({"sotn.CUE": CUE, f"{SOTN.upper()} (TRACK 1).BIN": "", f"{SOTN} (track 2).bin": ""},
                              [("sotn.CUE", "sotn.CUE"), (f"{SOTN.upper()} (TRACK 1).BIN", f"{SOTN} (Track 1).bin"),
                               (f"{SOTN} (track 2).bin", f"{SOTN} (Track 2).bin")]),  # saved as the .cue names them
    "a .cue whose .bin is missing, and a lone .bin": ({f"{SOTN}.cue": CUE, "sotn.bin": ""}, [("sotn.bin", "sotn.bin")]),
    "a .zip": ({"sotn.zip": ""}, [("sotn.zip", "sotn.zip")]),
    "nothing": ({"photo.jpg": "", "readme.txt": ""}, []),
    # a rip in a folder inside the one picked (unzipped into its own folder, or a "PS1" folder)
    "one folder down": ({f"{SOTN}/{SOTN}.cue": CUE, f"{SOTN}/{SOTN} (Track 1).bin": "", f"{SOTN}/{SOTN} (Track 2).bin": ""},
                        [(f"{SOTN}/{SOTN}.cue", f"{SOTN}.cue"), (f"{SOTN}/{SOTN} (Track 1).bin", f"{SOTN} (Track 1).bin"),
                         (f"{SOTN}/{SOTN} (Track 2).bin", f"{SOTN} (Track 2).bin")]),
    "three folders down, next to another game": (
        {"PS1/Metal Gear Solid/mgs.cue": 'FILE "mgs.bin" BINARY\n', "PS1/Metal Gear Solid/mgs.bin": "",
         "PS1/Castlevania/rip/game.cue": CUE, f"PS1/Castlevania/rip/{SOTN} (Track 1).bin": "",
         f"PS1/Castlevania/rip/{SOTN} (Track 2).bin": "", "PS1/readme.txt": ""},
        [("PS1/Castlevania/rip/game.cue", "game.cue"), (f"PS1/Castlevania/rip/{SOTN} (Track 1).bin", f"{SOTN} (Track 1).bin"),
         (f"PS1/Castlevania/rip/{SOTN} (Track 2).bin", f"{SOTN} (Track 2).bin")]),
    "a .cue and its .bin files in different folders": (
        {"sotn/sotn.cue": CUE, f"{SOTN} (Track 1).bin": "", f"bins/{SOTN} (Track 2).bin": ""},
        [("sotn/sotn.cue", "sotn.cue"), (f"{SOTN} (Track 1).bin", f"{SOTN} (Track 1).bin"),
         (f"bins/{SOTN} (Track 2).bin", f"{SOTN} (Track 2).bin")]),
    "a .zip in a folder": ({"downloads/sotn.zip": ""}, [("downloads/sotn.zip", "sotn.zip")]),
    "a .cue naming its files with Windows slashes": (
        {"a/sotn.cue": 'FILE "bins\\track1.bin" BINARY\n', "a/bins/track1.bin": ""},
        [("a/sotn.cue", "sotn.cue"), ("a/bins/track1.bin", "track1.bin")]),
}


def test_disc_files():
    for what, (folder, want) in FOLDERS.items():
        got = disc_files(list(folder), lambda name: folder[name])
        assert got == want, f"{what}: {got} != {want}"
        print("ok  ", what)


def test_unzip_disc():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        z = tmp / "sotn.zip"
        with zipfile.ZipFile(z, "w") as f:
            f.writestr(f"{SOTN}/{SOTN}.cue", CUE)
            f.writestr(f"{SOTN}/{SOTN} (Track 1).bin", b"\0" * 2352)
            f.writestr(f"{SOTN}/{SOTN} (Track 2).bin", b"\0" * 2352)
            f.writestr(f"{SOTN}/cover.jpg", b"")
        cue = unzip_disc(z, tmp)
        assert cue == tmp / f"{SOTN}.cue", cue
        assert sorted(p.name for p in tmp.iterdir()) == sorted(
            [f"{SOTN}.cue", f"{SOTN} (Track 1).bin", f"{SOTN} (Track 2).bin"]), list(tmp.iterdir())
        print("ok   a .zip unpacks to its .cue and .bin files (not the zip's folders or other files)")


if __name__ == "__main__":
    test_disc_files()
    test_unzip_disc()
    print("PASSED test_android_disc")
