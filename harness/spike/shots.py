import sys
exec(open("/home/claude/harness/smoke.py").read().split("core = ")[0])
from libretro import Session, DictOptionDriver
from libretro.drivers import ExplicitPathDriver
from PIL import Image
opts={"swanstation_Console_Enable8MBRAM":sys.argv[3],"swanstation_BIOS_PathNTSCU":"scph5501.bin","swanstation_GPU_Renderer":"Software"}
with Session("/home/claude/emu/swanstation/build/swanstation_libretro.so", sys.argv[1], options=DictOptionDriver(variables=opts),
             path=ExplicitPathDriver(system="/home/claude/harness/sys", save="/tmp/claude-0/sav")) as s:
    for f in range(1, int(sys.argv[2])+1):
        s.run()
        if f in tuple(int(x) for x in sys.argv[4].split(',')):
            fb = s.video.screenshot()
            if fb: (lambda b,w,h: Image.frombytes("RGB",(w,h),b,"raw","BGR;16",len(b)//h) if fb.pixel_format==2 else Image.frombytes("RGB",(w,h),b,"raw","BGRX",len(b)//h))(bytes(fb.data),fb.width,fb.height).resize((320,240)).save(f"/tmp/claude-0/f{f}.png"); print("shot", f, fb.width, fb.height, fb.pixel_format if hasattr(fb,'pixel_format') else '')
            else: print("noshot", f)
