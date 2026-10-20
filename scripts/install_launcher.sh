#!/usr/bin/env bash
# Installs the co-op playtest launcher (launcher/play.py) as a native Windows app in
# Emulators\SOTN-Coop: its own Python environment, the Windows SwanStation core, the co-op disc
# (built from your own disc: game data, never publish), a savestate library made with the
# Windows core, and one .bat per preset. Re-run after scripts/build_disc.sh to update.
#   scripts/install_launcher.sh [path/to/swanstation_libretro.dll]
set -euo pipefail
MOD="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$MOD/../.." && pwd)"
PY="$ROOT/.venv/bin/python"
WIN_EMU="$("$PY" -c "import sys; sys.path.insert(0, '$MOD/harness'); from coop_env import ENV, path; print(path(ENV['paths']['win_emulators']))")"
DEST="$WIN_EMU/SOTN-Coop"
APP="$DEST/app"
DLL="${1:-$DEST/app/bin/swanstation_libretro.dll}"
WINPY="$(cmd.exe /c "where python" 2>/dev/null | tr -d '\r' | grep -v WindowsApps | head -1)"
[ -n "$WINPY" ] || { echo "Windows Python not found (install python.org's Python 3.12+)"; exit 1; }
WINPY="$(wslpath -u "$WINPY")"

echo "== app files"
mkdir -p "$APP"/{harness,link,launcher,config,build/coop,bin,bios,.env/out/disc,.env/savestates} "$DEST/cards"
cp "$MOD"/harness/{emu,session,coop_env,module,savestates,bots,replay}.py "$APP/harness/"
cp "$MOD"/link/*.py "$APP/link/"
cp "$MOD"/launcher/play.py "$APP/launcher/"
cp "$MOD/env.example.toml" "$APP/env.example.toml"
cat > "$APP/env.toml" <<'TOML'
# The launcher's own layout (scripts/install_launcher.sh): everything relative to app/.
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
cp "$ROOT"/config/symbols.us.txt "$ROOT"/config/symbols.us.main.txt "$ROOT"/config/symbols.us.dra.txt "$APP/config/"
cp "$ROOT/build/coop/coop.map" "$APP/build/coop/"
cp "$MOD/.env/sys/scph5501.bin" "$APP/bios/"
[ -f "$DLL" ] && [ "$DLL" != "$APP/bin/swanstation_libretro.dll" ] && cp "$DLL" "$APP/bin/"
[ -f "$APP/bin/swanstation_libretro.dll" ] || { echo "need the Windows core: pass its path"; exit 1; }
echo "== co-op disc"
for f in sotn_coop.us.cue sotn_coop.us.bin; do  # only if changed (700 MB)
    cmp -s "$MOD/.env/out/disc/$f" "$APP/.env/out/disc/$f" || cp "$MOD/.env/out/disc/$f" "$APP/.env/out/disc/"
done

W() { wslpath -w "$1"; }
echo "== Python environment"
if [ ! -f "$DEST/venv/Scripts/python.exe" ]; then
    "$WINPY" -m venv "$(W "$DEST/venv")"
fi
"$DEST/venv/Scripts/python.exe" -m pip install -q --upgrade pip >/dev/null
"$DEST/venv/Scripts/python.exe" -m pip install -q "libretro.py==0.12.0" pygame-ce pillow
INDEX="$APP/.env/savestates/sotn_coop.us/index.json"
if [ ! -f "$INDEX" ] || [ "$APP/.env/out/disc/sotn_coop.us.bin" -nt "$INDEX" ]; then
    echo "== savestates (Windows core; about 30 s)"
    "$DEST/venv/Scripts/python.exe" "$(W "$APP/harness/savestates.py")" "$(W "$APP/.env/out/disc/sotn_coop.us.cue")" | grep -v '^\[' | tail -4
fi

echo "== presets"
rm -f "$DEST"/[0-9]\ *.bat  # the numbering changes between playtests
mk() {  # mk "file name" preset [extra args]
    printf '@echo off\r\ncd /d "%%~dp0"\r\nvenv\\Scripts\\python.exe app\\launcher\\play.py --preset %s %s\r\nif errorlevel 1 pause\r\n' "$2" "${3:-}" > "$DEST/$1.bat"
}
mk "1 Shared room fight" hall
mk "2 Teleport and respawn" teleport
mk "3 Save room (then run 4)" saveroom
mk "4 Resume from Load menu" resume
mk "5 Boss fight together" boss
mk "6 Cutscene together" cutscene
mk "7 Explore apart (pickups, map)" explore
mk "8 New game from scratch" newgame --fresh-cards
cp "$MOD/launcher/PLAYTEST.md" "$DEST/README-playtest.md" 2>/dev/null || true
echo "== installed in $DEST"
