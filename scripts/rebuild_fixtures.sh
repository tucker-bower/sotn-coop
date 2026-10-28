#!/bin/bash
# After a module change: the disc, Maria (and her patches), the savestate library, the M12
# fixtures and the debug/boss/scene starts. Savestates hold the module's code, so every one of
# them is stale after a rebuild (harness/README.md). About 15 minutes; the starts alone: make_debug_starts.py.
set -eo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PY=${PY:-/home/tucker/sotn-decomp-coop/.venv/bin/python}
cd "$ROOT" && scripts/build_disc.sh 2>&1 | tail -1
make -C maria >/dev/null 2>&1 && $PY maria/make_patches.py .env/out/maria 2>&1 | tail -1
cd "$ROOT/harness"
DISC=$($PY -c "from module import COOP_DISC; print(COOP_DISC)")
$PY savestates.py "$DISC" 2>&1 | grep -v "^\[" | tail -1
$PY fixtures_m12.py 2>&1 | grep -v "^\[" | tail -1
rm -rf "$ROOT/.env/fixtures/debug-starts"
$PY "$ROOT/scripts/make_debug_starts.py" 2>&1 | grep -v "^\[" | tail -1
