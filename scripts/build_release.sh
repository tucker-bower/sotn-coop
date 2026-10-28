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
STAGE="$OUT/stage"
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
cp "$MOD"/launcher/*.py "$A/launcher/"
cp -r "$MOD/launcher/assets" "$A/launcher/"
cp "$MOD"/link/*.py "$A/link/"
cp "$MOD"/patcher/{bps,patcher,sectors}.py "$MOD/.env/release/sotn-coop.bps" "$MOD/.env/release/manifest.json" "$A/patcher/"
# Maria's patches (design/M8 §4): our changes only; the launcher applies them to the player's DXC disc.
mkdir -p "$A/patcher/maria"
cp "$MOD"/.env/out/maria/{maria.json,maria.bps,maria-vh.bps,maria-vb.bps} "$A/patcher/maria/"
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
# The licences (NOTICE is the README the installer shows first; full texts in licenses/)
cp "$MOD/NOTICE" "$A/LICENSES/README.txt"
cp "$MOD/LICENSE" "$A/LICENSES/AGPL-3.0.txt"
cp "$MOD"/licenses/* "$A/LICENSES/"
cp "$MOD/README.md" "$A/README.md"

echo "== no game data in the installer"
if find "$STAGE" -iname "*.bin" ! -name openbios.bin -o -iname "*.cue" -o -iname "*.state" -o -iname "*.mcd" | grep -q .; then
    echo "game data found in the stage: refusing" >&2
    find "$STAGE" -iname "*.bin" ! -name openbios.bin -o -iname "*.cue" -o -iname "*.state" -o -iname "*.mcd" >&2
    exit 1
fi

echo "== installer"
cp "$MOD/installer/sotn-coop.iss" "$OUT/sotn-coop.iss"
(cd "$OUT" && "$EMU/InnoSetup/ISCC.exe" /Q "/DVersion=$VERSION" "/DStage=$(W "$STAGE")" "/DOut=$(W "$OUT")" "sotn-coop.iss" </dev/null)
rm -f "$OUT/sotn-coop.iss"
ls -l "$OUT"/SOTN-Coop-setup-*.exe
