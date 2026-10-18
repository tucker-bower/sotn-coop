import sys, time, libretro
# libretro.py 0.12 bug: NULL frame pointers arrive as value None, not 0. Treat them as "dupe frame".
from libretro.drivers.environment import composite as _c
_orig = _c.CompositeEnvironmentDriver.video_refresh
def _vr(self, data, w, h, p):
    if data is None or data.value is None:
        return self._video.refresh(_c.FrameBufferSpecial.DUPE, w, h, p)
    return _orig(self, data, w, h, p)
_c.CompositeEnvironmentDriver.video_refresh = _vr
from libretro import Session, DictOptionDriver
core = "/home/claude/emu/swanstation/build/swanstation_libretro.so"
disc = sys.argv[1]; frames = int(sys.argv[2]); out = sys.argv[3]
opts = {"swanstation_Console_Enable8MBRAM": "true", "swanstation_BIOS_PathNTSCU": "scph5501.bin",
        "swanstation_GPU_Renderer": "Software", "swanstation_CPU_ExecutionMode": "Recompiler"}
from libretro.drivers import ExplicitPathDriver
t=time.time()
with Session(core, disc, options=DictOptionDriver(variables=opts),
             path=ExplicitPathDriver(system="/home/claude/harness/sys", save="/tmp/claude-0/sav", assets="/tmp/claude-0/ca", playlist="/tmp/claude-0/pl")) as s:
    for i in range(frames): s.run()
    ram = s.core.get_memory_data(libretro.RETRO_MEMORY_SYSTEM_RAM) if hasattr(s.core,'get_memory_data') else None
    sz = s.core.get_memory_size(libretro.RETRO_MEMORY_SYSTEM_RAM)
    print("frames", frames, "secs %.1f" % (time.time()-t), "ram size", hex(sz))
    fb = s.video.screenshot()
    if fb:
        from PIL import Image
        Image.frombytes("RGBA" if len(fb.data)==fb.width*fb.height*4 else "RGB", (fb.width, fb.height), bytes(fb.data)).save(out)
        print("saved", out, fb.width, fb.height)
