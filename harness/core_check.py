"""Checks a SwanStation core build on this machine (M13: our patched core, every platform).

    python harness/core_check.py <core> <disc .cue> <bios dir> [frames]

Boots the disc with no input for `frames` frames (default 1500: the title), then prints the
RAM's and VRAM's hashes, the frame size and the savestate size, and loads the state back and
runs again: the two runs must match. Run it with each platform's core and compare the lines:
the same core source on the same disc and BIOS gives the same hashes everywhere. Stdlib plus
libretro.py only (no env.toml), so it runs as-is with the Windows launcher's Python.
"""

import hashlib
import sys
import tempfile

import libretro
from libretro import DictOptionDriver, Session
from libretro.drivers import ExplicitPathDriver
from libretro.drivers.audio.array import ArrayAudioDriver
from libretro.drivers.environment import composite as _composite
from libretro.drivers.input.iterable import IterableInputDriver

# libretro.py 0.12: a NULL frame pointer arrives as value None (emu.py has the same fix)
_orig_video_refresh = _composite.CompositeEnvironmentDriver.video_refresh


def _video_refresh(self, data, width, height, pitch):
    if data is None or data.value is None:
        return self._video.refresh(_composite.FrameBufferSpecial.DUPE, width, height, pitch)
    return _orig_video_refresh(self, data, width, height, pitch)


_composite.CompositeEnvironmentDriver.video_refresh = _video_refresh

OPTIONS = {
    "swanstation_Console_Enable8MBRAM": "true",
    "swanstation_BIOS_PathNTSCU": "scph5501.bin",
    "swanstation_GPU_Renderer": "Software",
    "swanstation_CPU_ExecutionMode": "Recompiler",
}


class _NoPads(IterableInputDriver):
    def __init__(self):
        super().__init__(iter(()))

    def state(self, port, device, index, id):
        return 0


def main(core, disc, bios_dir, frames=1500):
    tmp = tempfile.mkdtemp(prefix="coop-core-")
    with Session(core, disc, input=_NoPads(), audio=ArrayAudioDriver(),
                 options=DictOptionDriver(variables=OPTIONS),
                 path=ExplicitPathDriver(system=bios_dir, save=tmp, assets=tmp, playlist=tmp)) as s:
        c = s.core

        def run(n):
            for _ in range(n):
                s.run()
            ram = hashlib.sha256(bytes(c.get_memory(libretro.RETRO_MEMORY_SYSTEM_RAM))).hexdigest()[:16]
            vram = c.get_memory(libretro.RETRO_MEMORY_VIDEO_RAM)
            vh = hashlib.sha256(bytes(vram)).hexdigest()[:16] if vram is not None else "none"
            return ram, vh, len(vram) if vram is not None else 0

        a = run(frames)
        buf = bytearray(c.serialize_size())
        assert c.serialize(buf), "serialize failed"
        b = run(120)
        assert c.unserialize(bytes(buf)), "unserialize failed"
        b2 = run(120)
        print(f"after {frames} frames: ram {a[0]} vram {a[1]} ({a[2]} bytes) state {len(buf)} bytes")
        print(f"+120 frames: ram {b[0]} vram {b[1]}; from the state again: {'same' if b == b2 else 'DIFFERENT'}")
        return 0 if b == b2 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2], sys.argv[3], *(int(a) for a in sys.argv[4:5])))
