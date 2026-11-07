#!/bin/bash
# After a module change: the disc, Maria (and her patches), the savestate library, the M12
# fixtures and the debug/boss/scene starts. Savestates hold the module's code, so every one of
# them is stale after a rebuild (harness/README.md). About 15 minutes; the starts alone: make_debug_starts.py.
set -eo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PY=${PY:-$ROOT/.env/src/sotn-decomp/.venv/bin/python}
python3 "$ROOT/scripts/disk_space.py"  # stop before the disk fills (AGENTS.md)
cd "$ROOT" && scripts/build_disc.sh 2>&1 | tail -1
make -C characters/maria-dx >/dev/null 2>&1 && $PY characters/maria-dx/make_patches.py .env/out/maria 2>&1 | tail -1
cd "$ROOT/harness"
DISC=$($PY -c "from module import COOP_DISC; print(COOP_DISC)")
$PY savestates.py "$DISC" 2>&1 | grep -v "^\[" | tail -1
$PY fixtures_m12.py 2>&1 | grep -v "^\[" | tail -1
rm -rf "$ROOT/.env/fixtures/debug-starts"
$PY "$ROOT/scripts/make_debug_starts.py" 2>&1 | grep -v "^\[" | tail -1
$PY "$ROOT/scripts/export_test_castles.py" | tail -1  # the test castles the app ships (D136)
# The release patch too: the launcher's UI flows (launcher/uxdriver.py) make their disc with it, and
# a stale one tested an old game (2026-10-31: test_castles failed on the 10-28 patch's mailbox).
DISKS=$($PY -c "import sys; sys.path.insert(0, '$ROOT/harness'); from coop_env import DISKS; print(DISKS)")
$PY "$ROOT/patcher/patcher.py" make "$DISKS/Castlevania - Symphony of the Night (USA) (Track 1).bin" \
    "$ROOT/.env/out/disc/sotn_coop.us.bin" --out "$ROOT/.env/release" \
    --version "$(grep -oP 'VERSION = "\K[^"]+' "$ROOT/launcher/report.py")" | tail -1
