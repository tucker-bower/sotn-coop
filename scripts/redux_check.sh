#!/usr/bin/env bash
# Runs harness/redux_check.lua in the Windows PCSX-Redux, headless (no window), against the co-op disc.
# Usage: scripts/redux_check.sh [disc.cue]   (default: the last scripts/build_disc.sh output)
set -euo pipefail
COOP="$(cd "$(dirname "$0")/.." && pwd)"
if [ -f "$COOP/.env/src/sotn-decomp/.venv/bin/python" ]; then
    PY="$COOP/.env/src/sotn-decomp/.venv/bin/python"
else
    PY="$COOP/../../.venv/bin/python"
fi
REDUX="$("$PY" -c "import sys; sys.path.insert(0, '$COOP/harness'); from coop_env import ENV, path; print(path(ENV['paths']['win_emulators']) / 'PCSX-Redux')")"
DISC="${1:-$COOP/.env/out/disc/sotn_coop.us.cue}"
# Its work files on the Windows side: it no longer opens a log, memory cards or a script on the WSL
# share (\\wsl.localhost\...; 2026-10-27). The disc it still reads from there.
WORK="$(wslpath "$(cmd.exe /c echo %TEMP% 2>/dev/null | tr -d '\r')")/sotn-coop-redux"
mkdir -p "$WORK"
rm -f "$WORK"/memcard*.mcd "$WORK"/log.txt "$WORK"/redux.log  # fresh, empty memory cards every run
cp "$COOP/.env/sys/scph5501.bin" "$WORK/bios.bin"

# PCSX-Redux is a Windows program: give it Windows paths, and copy the Lua script to where it can read it.
{
    echo "COOP_SYMBOLS = {"
    "$PY" - <<EOF
import sys; sys.path.insert(0, "$COOP/harness")
from emu import SYMBOLS; from module import symbols
for k in ("g_GameState", "g_GameStep", "g_StageId", "g_Timer", "g_Tilemap", "g_GameEngineStep"):
    print(f"  {k} = 0x{SYMBOLS[k]:08X},")
print(f"  g_CoopLink = 0x{symbols()['g_CoopLink']:08X},")
EOF
    echo "}"
    echo "COOP_RESULT_PATH = [[$(wslpath -w "$WORK/log.txt")]]"
    cat "$COOP/harness/redux_check.lua"
} > "$WORK/check.lua"

cd "$REDUX"
timeout 900 ./pcsx-redux.exe -cli -stdout -no-webserver -no-gdb -no-debugger -8mb -fastboot \
    -bios "$(wslpath -w "$WORK/bios.bin")" \
    -memcard1 "$(wslpath -w "$WORK/memcard1.mcd")" -memcard2 "$(wslpath -w "$WORK/memcard2.mcd")" \
    -iso "$(wslpath -w "$DISC")" -run -dofile "$(wslpath -w "$WORK/check.lua")" \
    -logfile "$(wslpath -w "$WORK/redux.log")" >/dev/null 2>&1 || true
cat "$WORK/log.txt" 2>/dev/null || echo "no output: see $WORK/redux.log"
grep -q "^RESULT PASS" "$WORK/log.txt"
