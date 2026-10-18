import sys, time, struct, libretro
exec(open("/home/claude/harness/smoke.py").read().split("core = ")[0])  # reuse imports + patch
from libretro import Session, DictOptionDriver
from libretro.drivers import ExplicitPathDriver
import logging
class H(logging.Handler):
    def emit(self, r):
        try: m = r.getMessage()
        except Exception: m = str(r.msg) + str(r.args)
        if any(k in m.lower() for k in ("bios","error","fail","cd","disc","boot","exe","ram")): print("LOG", m[:200])
logging.getLogger().addHandler(H()); logging.getLogger().setLevel(logging.DEBUG)
core="/home/claude/emu/swanstation/build/swanstation_libretro.so"
opts={"swanstation_Console_Enable8MBRAM":"true","swanstation_BIOS_PathNTSCU":"scph5501.bin","swanstation_GPU_Renderer":"Software"}
SYM={"g_GameState":0x8003C734,"g_GameTimer":0x8003C8C4,"g_Timer":0x8003C998,"g_GameStep":0x80073060}
with Session(core, sys.argv[1], options=DictOptionDriver(variables=opts),
             path=ExplicitPathDriver(system="/home/claude/harness/sys", save="/tmp/claude-0/sav")) as s:
    mem = s.core.get_memory(libretro.RETRO_MEMORY_SYSTEM_RAM) if hasattr(s.core,"get_memory") else None
    for f in range(0, int(sys.argv[2])+1):
        s.run()
        if f % 300 == 0:
            ram = s.core.get_memory(libretro.RETRO_MEMORY_SYSTEM_RAM)
            vals = {k: struct.unpack_from("<I", ram, v-0x80000000)[0] for k,v in SYM.items()}
            # sniff the RAM_SIZE effect: anything nonzero above 2MB?
            hi = any(ram[0x280000:0x280100])
            print(f, vals, "8MB-area-nonzero:", hi)
