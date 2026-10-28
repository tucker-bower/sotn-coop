#!/usr/bin/env bash
# Builds the Android app (design/M9-android.md): .env/android/SOTN-Coop-<version>.apk, for arm64
# phones and x86_64 (the test emulators). Needs scripts/android_setup.sh once, and a disc built
# by scripts/build_disc.sh (the patch is made from it, as for the PC installer).
#
#   android/build.sh [version] [arch ...]      (default: the launcher's version; both arches)
set -euo pipefail
MOD="$(cd "$(dirname "$0")/.." && pwd)"
A="${ANDROID_HOME:-$HOME/android}"
if [ -f "$MOD/.env/src/sotn-decomp/sotn.sh" ]; then ROOT="$MOD/.env/src/sotn-decomp"; else ROOT="$(cd "$MOD/../.." && pwd)"; fi
PY="$ROOT/.venv/bin/python"
VERSION="${1:-$(grep -oP 'VERSION = "\K[^"]+' "$MOD/launcher/report.py")}"
shift || true
ARCHES=("${@:-arm64-v8a x86_64}")
ARCHES=(${ARCHES[@]})
OUT="$MOD/.env/android"
STAGE="$OUT/app"
DISKS="$("$PY" -c "import sys; sys.path.insert(0, '$MOD/harness'); from coop_env import DISKS; print(DISKS)")"
EMU="$("$PY" -c "import sys; sys.path.insert(0, '$MOD/harness'); from coop_env import ENV, path; print(path(ENV['paths']['win_emulators']))")"

echo "== patch (from your disc and our build: our changes only)"
"$PY" "$MOD/patcher/patcher.py" make "$DISKS/Castlevania - Symphony of the Night (USA) (Track 1).bin" \
    "$MOD/.env/out/disc/sotn_coop.us.bin" --out "$MOD/.env/release" --version "$VERSION"

echo "== stage $STAGE"
rm -rf "$STAGE"
mkdir -p "$STAGE"/{harness,launcher,link,patcher/maria,config,build/coop,bios,bin}
cp "$MOD"/harness/{emu,session,coop_env,module,savestates,bots}.py "$STAGE/harness/"
cp "$MOD"/launcher/*.py "$STAGE/launcher/"
cp -r "$MOD/launcher/assets" "$STAGE/launcher/"
cp "$MOD"/link/*.py "$STAGE/link/"
cp "$MOD"/patcher/{bps,patcher,sectors}.py "$MOD/.env/release/sotn-coop.bps" "$MOD/.env/release/manifest.json" "$STAGE/patcher/"
cp "$MOD"/.env/out/maria/{maria.json,maria.bps,maria-vh.bps,maria-vb.bps} "$STAGE/patcher/maria/"
cp "$ROOT"/config/symbols.us.txt "$ROOT"/config/symbols.us.main.txt "$ROOT"/config/symbols.us.dra.txt "$STAGE/config/"
cp "$ROOT/build/coop/coop.map" "$STAGE/build/coop/"
cp "$EMU/PCSX-Redux/openbios.bin" "$STAGE/bios/openbios.bin"
cp "$MOD/env.example.toml" "$MOD/android/main.py" "$STAGE/"
mkdir -p "$STAGE/LICENSES" && cp "$MOD/NOTICE" "$STAGE/LICENSES/README.txt" && cp "$MOD/LICENSE" "$STAGE/LICENSES/AGPL-3.0.txt" && cp "$MOD"/licenses/* "$STAGE/LICENSES/"
# libretro.py: pure Python (its sample cores and their GL libraries aren't needed)
SP="$("$PY" -c "import libretro, os; print(os.path.dirname(os.path.dirname(libretro.__file__)))")"
cp -r "$SP/libretro" "$STAGE/libretro" && rm -rf "$STAGE/libretro/samples"
find "$STAGE" -name __pycache__ -prune -exec rm -rf {} +
for arch in "${ARCHES[@]}"; do
    mkdir -p "$STAGE/bin/$arch" && cp "$A/cores/$arch/swanstation_libretro_android.so" "$STAGE/bin/$arch/"
done

echo "== no game data in the app"
if find "$STAGE" -iname "*.bin" ! -name openbios.bin -o -iname "*.cue" -o -iname "*.iso" -o -iname "*.state" -o -iname "*.mcd" | grep -q .; then
    echo "game data found in the stage: refusing" >&2
    exit 1
fi

echo "== apk (python-for-android)"
ARCH_ARGS=(); for arch in "${ARCHES[@]}"; do ARCH_ARGS+=(--arch "$arch"); done
cd "$OUT"
ANDROIDSDK="$A" ANDROIDNDK="$A/ndk/25.2.9519653" ANDROIDAPI=34 NDKAPI=24 \
"$A/p4a-venv/bin/p4a" apk --private "$STAGE" --package org.sotncoop.app --name "SOTN Co-op" \
    --version "${VERSION%%-*}" --bootstrap sdl2 --requirements python3,pygame,pyjnius,android \
    "${ARCH_ARGS[@]}" --dist-name sotncoop --orientation landscape \
    --icon "$MOD/launcher/assets/icon.png" --permission INTERNET --permission ACCESS_NETWORK_STATE \
    --permission ACCESS_WIFI_STATE --permission CHANGE_WIFI_MULTICAST_STATE --permission WAKE_LOCK \
    --local-recipes "$MOD/android/recipes" --ignore-setup-py > "$OUT/p4a.log" 2>&1 || { tail -40 "$OUT/p4a.log"; exit 1; }
APK=$(ls -t "$OUT"/*.apk | head -1)
mv "$APK" "$OUT/SOTN-Coop-$VERSION.apk"
ls -l "$OUT/SOTN-Coop-$VERSION.apk"
