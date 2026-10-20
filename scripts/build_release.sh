#!/usr/bin/env bash
# Builds the Windows installer, SOTN-Coop-setup-<version>.exe (design/M6-playable-build.md).
#   scripts/build_release.sh [version]
# Run after scripts/build_disc.sh. Needs the Windows Python and Inno Setup (in Emulators\InnoSetup)
# and the cached downloads in .env/cache (python embeddable zip).
#
# The installer holds NO game data: python.org's embeddable Python and the launcher's packages,
# our source, the SwanStation core, OpenBIOS (MIT), and the patch (our changes only, D71). The
# co-op disc is made from the player's own disc on first launch.
set -euo pipefail
MOD="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "$MOD/.env/src/sotn-decomp/sotn.sh" ]; then
    ROOT="$MOD/.env/src/sotn-decomp"
else
    ROOT="$(cd "$MOD/../.." && pwd)"
fi
PY="$ROOT/.venv/bin/python"
DISKS="$("$PY" -c "import sys; sys.path.insert(0, '$MOD/harness'); from coop_env import DISKS; print(DISKS)")"
VERSION="${1:-$(grep -oP 'VERSION = "\K[^"]+' "$MOD/launcher/report.py")}"
EMU="$("$PY" -c "import sys; sys.path.insert(0, '$MOD/harness'); from coop_env import ENV, path; print(path(ENV['paths']['win_emulators']))")"
OUT="$EMU/SOTN-Coop-release"
STAGE="$MOD/.env/release/stage"
CACHE="$MOD/.env/cache"
PYZIP="$CACHE/python-3.14.2-embed-amd64.zip"
WINPY="$EMU/SOTN-Coop/venv/Scripts/python.exe"
VENV_SP="$EMU/SOTN-Coop/venv/Lib/site-packages"
DLL="$EMU/SOTN-Coop/app/bin/swanstation_libretro.dll"
OPENBIOS="$EMU/PCSX-Redux/openbios.bin"
W() { wslpath -w "$1"; }

echo "== patch (from your disc and our build: our changes only)"
"$PY" "$MOD/patcher/patcher.py" make "$DISKS/Castlevania - Symphony of the Night (USA) (Track 1).bin" \
    "$MOD/.env/out/disc/sotn_coop.us.bin" --out "$MOD/.env/release" --version "$VERSION"

echo "== stage $STAGE"
rm -rf "$STAGE/app"
mkdir -p "$STAGE/python/Lib/site-packages" "$STAGE/app"/{harness,launcher,link,patcher,config,build/coop,bin,bios,LICENSES}
if [ ! -d "$STAGE/python/Lib/site-packages/pygame" ]; then
    python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$PYZIP" "$STAGE/python"
    PTH=$(ls "$STAGE"/python/python3*._pth)
    # The embedded Python ignores the script's folder: our folders are listed here instead (also for
    # the worker processes the games run in).
    printf 'python314.zip\n.\nLib\\site-packages\n..\\app\\launcher\n..\\app\\harness\n..\\app\\patcher\n..\\app\n' > "$PTH"
    if [ -d "$VENV_SP/pygame" ]; then
        cp -r "$VENV_SP"/PIL "$VENV_SP"/libretro* "$VENV_SP"/pillow* "$VENV_SP"/pygame* "$STAGE/python/Lib/site-packages/"
    else
        "$WINPY" -m pip install -q --target "$(W "$STAGE/python/Lib/site-packages")" pygame-ce "libretro.py==0.12.0" pillow </dev/null
    fi
fi

A="$STAGE/app"
cp "$MOD"/harness/{emu,session,coop_env,module,savestates,bots}.py "$A/harness/"
cp "$MOD"/launcher/{app,gameview,paths,archive,report,debugstarts,play}.py "$A/launcher/"
cp "$MOD"/link/*.py "$A/link/"
cp "$MOD"/patcher/{bps,patcher}.py "$MOD/.env/release/sotn-coop.bps" "$MOD/.env/release/manifest.json" "$A/patcher/"
cp "$ROOT"/config/symbols.us.txt "$ROOT"/config/symbols.us.main.txt "$ROOT"/config/symbols.us.dra.txt "$A/config/"
cp "$ROOT/build/coop/coop.map" "$A/build/coop/"
cp "$DLL" "$A/bin/"
cp "$OPENBIOS" "$A/bios/openbios.bin"
cp "$MOD/env.example.toml" "$A/"
cat > "$A/env.toml" <<'TOML'
# The installed launcher's layout (scripts/build_release.sh): everything relative to app/.
[paths]
repo = "."
disks = ".env/out/disc"
env = ".env"
[tools]
swanstation_core = "bin/swanstation_libretro.dll"
bios_dir = "bios"
savestates = ".env/savestates"
out = ".env/out"
TOML
cat > "$A/LICENSES/README.txt" <<'TXT'
SOTN Co-op

A co-op mod for Castlevania: Symphony of the Night. It contains no game data: on first launch
it makes the co-op disc from YOUR OWN copy of the game (USA, SLUS-00067). Castlevania and
Symphony of the Night are trademarks of Konami; this project is not affiliated with Konami.

What's included, and under which licence:
- SOTN Co-op (the launcher, the co-op module, the patch): AGPL-3.0, like sotn-decomp, which it
  is built on. Source: https://github.com/tucker-bower/sotn-decomp-coop
- SwanStation (bin/swanstation_libretro.dll), the PlayStation emulator core: GPL-3.0.
  Source: https://github.com/libretro/swanstation
- OpenBIOS (bios/openbios.bin), an open-source PlayStation BIOS from PCSX-Redux: MIT, see
  OpenBIOS-LICENSE.txt. Source: https://github.com/grumpycoders/pcsx-redux (src/mips/openbios)
- Python (python/), python.org's embeddable distribution: PSF License.
- pygame-ce (LGPL-2.1), libretro.py (MIT), Pillow (MIT-CMU): in python/Lib/site-packages.
TXT
cat > "$A/LICENSES/OpenBIOS-LICENSE.txt" <<'TXT'
MIT License

Copyright (c) 2019-2024 PCSX-Redux authors

Permission is hereby granted, free of charge, to any person obtaining a copy of this software
and associated documentation files (the "Software"), to deal in the Software without
restriction, including without limitation the rights to use, copy, modify, merge, publish,
distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING
BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
TXT
cp "$MOD/README.md" "$A/README.md"

echo "== no game data in the installer"
if find "$STAGE" -iname "*.bin" ! -name openbios.bin -o -iname "*.cue" -o -iname "*.state" -o -iname "*.mcd" | grep -q .; then
    echo "game data found in the stage: refusing" >&2
    find "$STAGE" -iname "*.bin" ! -name openbios.bin -o -iname "*.cue" -o -iname "*.state" -o -iname "*.mcd" >&2
    exit 1
fi

echo "== installer"
"$EMU/InnoSetup/ISCC.exe" /Q "/DVersion=$VERSION" "/DStage=$(W "$STAGE")" "/DOut=$(W "$OUT")" "$(W "$MOD/installer/sotn-coop.iss")"
ls -l "$OUT"/SOTN-Coop-setup-*.exe
