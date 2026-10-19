#!/usr/bin/env bash
# Builds the co-op disc image from the user's own disc (disks/sotn.us.cue, already extracted by bootstrap).
# Output: mods/co-op/.env/out/disc/sotn_coop.us.cue + .bin   (game data: never commit, never publish)
# Mirrors upstream's `make disk_debug`, with our module in the TT_000 (familiar) slot.
set -euo pipefail

COOP="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$COOP/../.." && pwd)"
OUT="$COOP/.env/out/disc"
cd "$ROOT"
# shellcheck disable=SC1091
. .venv/bin/activate
export VERSION=us

echo "== compile game (unchecked: the image differs from retail by design)"
SKIP_CHECK=1 ./sotn.sh build us >/dev/null
echo "== compile co-op module"
make -s -C "$COOP/module"
cp build/coop/coop.bin build/us/TT_000.BIN
echo "== relink with the new disc layout"
# Upstream regenerates the tracked include/lba_us.h here; we restore it afterwards to keep git clean.
./sotn.sh disk --lba-dry-run > include/lba_us.h
ninja >/dev/null
./sotn.sh disk >/dev/null
git checkout -q include/lba_us.h
rm build/us/TT_000.BIN && ninja >/dev/null  # put the matching build back (doctor checks it)

mkdir -p "$OUT"
mv build/sotn.us.bin "$OUT/sotn_coop.us.bin"
sed 's/sotn\.us\.bin/sotn_coop.us.bin/' build/sotn.us.cue > "$OUT/sotn_coop.us.cue"
rm -f build/sotn.us.cue
echo "== built $OUT/sotn_coop.us.cue"
