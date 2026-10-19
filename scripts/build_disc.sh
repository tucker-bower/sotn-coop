#!/usr/bin/env bash
# Builds the co-op disc image from the user's own disc (disks/sotn.us.cue, already extracted by bootstrap).
# Output: mods/co-op/.env/out/disc/sotn_coop.us.cue + .bin   (game data: never commit, never publish)
#
# Mirrors upstream's `make disk`, with two changes (module/coop_api.h and boot.c explain why):
#   - DRA is built with its co-op hooks (COOP=1), and the module's boot stub is appended to
#     DRA.BIN, inside its last CD sector;
#   - COOP.BIN (the module) is added after every retail file.
# No retail file may move: scripts/check_disc_layout.py enforces it.
set -euo pipefail

MOD="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$MOD/../.." && pwd)"
OUT="$MOD/.env/out/disc"
cd "$ROOT"
# shellcheck disable=SC1091
. .venv/bin/activate
export VERSION=us
DRA_END=$((0x801b9870 - 0x800a0000))   # DRA.BIN's size; CoopBoot is linked to run right behind it
LIST=config/disk.us.lba

restore() {  # leave upstream's tracked file list and build dir as we found them
    git checkout -q "$LIST"
    rm -f build/us/COOP.BIN
}
trap restore EXIT

echo "== compile game with the co-op hooks (unchecked: the image differs from retail by design)"
COOP=1 SKIP_CHECK=1 ./sotn.sh build us >/dev/null
dra_end=$(awk '$2 == "dra_data_VRAM_END" {print $1}' build/us/dra.map)
if [ "$dra_end" != "0x801b9870" ]; then
    echo "DRA's image now ends at $dra_end, not 0x801b9870: a COOP hook changed DRA's size" >&2
    exit 1
fi

echo "== compile co-op module"
make -s -C "$MOD/module"
truncate -s "$DRA_END" build/us/DRA.BIN
cat build/coop/boot.bin >> build/us/DRA.BIN
cp build/coop/COOP.BIN build/us/COOP.BIN
# After the last data file (the CD-DA track stays last).
sed -i 's|^SD/CD1.DA;1,A,|COOP.BIN;1,N,20261018-000000-36\n&|' "$LIST"

echo "== master the disc"
COOP=1 SKIP_CHECK=1 ./sotn.sh disk >/dev/null
mkdir -p "$OUT"
mv build/sotn.us.bin "$OUT/sotn_coop.us.bin"
sed 's/sotn\.us\.bin/sotn_coop.us.bin/' build/sotn.us.cue > "$OUT/sotn_coop.us.cue"
rm -f build/sotn.us.cue
python3 "$MOD/scripts/check_disc_layout.py" disks/sotn.us.cue "$OUT/sotn_coop.us.cue"

echo "== restore the matching build (checked against retail)"
restore
./sotn.sh build us >/dev/null
echo "== built $OUT/sotn_coop.us.cue"
