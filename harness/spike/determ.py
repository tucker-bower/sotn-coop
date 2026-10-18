import sys, hashlib
exec(open("/home/claude/harness/smoke.py").read().split("core = ")[0])
from libretro import Session, DictOptionDriver
from libretro.drivers import ExplicitPathDriver
import libretro
opts={"swanstation_Console_Enable8MBRAM":"true","swanstation_BIOS_PathNTSCU":"scph5501.bin","swanstation_GPU_Renderer":"Software"}
def run():
    hs=[]
    with Session("/home/claude/emu/swanstation/build/swanstation_libretro.so", sys.argv[1], options=DictOptionDriver(variables=opts),
                 path=ExplicitPathDriver(system="/home/claude/harness/sys", save="/tmp/claude-0/sav")) as s:
        for f in range(1, 2401):
            s.run()
            if f % 600 == 0: hs.append(hashlib.sha1(bytes(s.core.get_memory(libretro.RETRO_MEMORY_SYSTEM_RAM))).hexdigest()[:10])
    return hs
a=run(); b=run(); print(a); print(b); print("DETERMINISTIC" if a==b else "DIVERGED")
