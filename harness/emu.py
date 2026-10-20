"""Headless, frame-stepped SOTN emulator for tests: SwanStation (libretro) driven from Python.

    with Emu(disc) as emu:
        emu.step(60, p1="right")              # hold right for 60 frames
        x = emu.read("g_Player")              # u32 at a decomp symbol
        state = emu.save_state(); emu.load_state(state)

Deterministic by construction: fixed core options, empty memory cards in a fresh temp dir,
no wall-clock input. Two Emu instances fed the same inputs produce identical RAM (lockstep.py).
"""

import re
import struct
import tempfile
from pathlib import Path

import libretro
from libretro import DictOptionDriver, Session
from libretro.drivers import ExplicitPathDriver
from libretro.drivers.audio.array import ArrayAudioDriver
from libretro.drivers.environment import composite as _composite
from libretro.drivers.input.iterable import IterableInputDriver

from coop_env import BIOS, REPO, TOOLS

# libretro.py 0.12 bug: a NULL frame pointer arrives as value None, not 0. Treat it as "dupe frame".
_orig_video_refresh = _composite.CompositeEnvironmentDriver.video_refresh


def _video_refresh(self, data, width, height, pitch):
    if data is None or data.value is None:
        return self._video.refresh(_composite.FrameBufferSpecial.DUPE, width, height, pitch)
    return _orig_video_refresh(self, data, width, height, pitch)


_composite.CompositeEnvironmentDriver.video_refresh = _video_refresh

# libretro joypad ids. SwanStation maps cross=B, circle=A, square=Y, triangle=X.
BUTTONS = {
    "cross": 0, "square": 1, "select": 2, "start": 3, "up": 4, "down": 5, "left": 6, "right": 7,
    "circle": 8, "triangle": 9, "l1": 10, "r1": 11, "l2": 12, "r2": 13, "l3": 14, "r3": 15,
}
_JOYPAD_MASK = 256
ENTITY_SIZE = 0xBC


def pad(buttons):
    """'right+cross' / ['right', 'cross'] / int bitmask -> libretro bitmask."""
    if isinstance(buttons, int):
        return buttons
    if isinstance(buttons, str):
        buttons = [b for b in buttons.split("+") if b]
    return sum(1 << BUTTONS[b] for b in buttons)


class _PadDriver(IterableInputDriver):
    """Holds the current button mask per port; the harness sets it before each frame."""

    def __init__(self):
        super().__init__(max_users=2)
        self.pads = [0, 0]

    def poll(self):
        pass

    def state(self, port, device, index, id):
        if int(device) != int(libretro.InputDevice.JOYPAD) or not 0 <= port < 2:
            return 0
        mask = self.pads[port]
        return mask if id == _JOYPAD_MASK else (mask >> id) & 1


class _NullAudioDriver(ArrayAudioDriver):
    """Discards audio so long runs don't grow memory."""

    def sample(self, left, right):
        pass

    def sample_batch(self, frames):
        return len(frames) // 2


def load_symbols(files=("symbols.us.txt", "symbols.us.main.txt", "symbols.us.dra.txt")):
    """name -> address from the decomp's linker symbol lists (globals that are always resident)."""
    syms = {}
    for name in files:
        for line in (REPO / "config" / name).read_text().splitlines():
            m = re.match(r"\s*(\w+)\s*=\s*(0x[0-9A-Fa-f]+);", line)
            if m:
                syms[m[1]] = int(m[2], 16)
    return syms


SYMBOLS = load_symbols()

OPTIONS = {
    "swanstation_Console_Enable8MBRAM": "true",
    "swanstation_BIOS_PathNTSCU": "scph5501.bin",
    "swanstation_GPU_Renderer": "Software",
    "swanstation_CPU_ExecutionMode": "Recompiler",
}


if BIOS:
    OPTIONS["swanstation_BIOS_PathNTSCU"] = BIOS.name


class Emu:
    def __init__(self, disc, ram_8mb=True, options=None, audio=False):
        """audio: keep the core's sound (take_audio() drains it), for real-time play."""
        opts = dict(OPTIONS, swanstation_Console_Enable8MBRAM="true" if ram_8mb else "false")
        opts.update(options or {})
        self._tmp = tempfile.TemporaryDirectory(prefix="coop-emu-")  # fresh, empty memory cards
        self._input = _PadDriver()
        self._audio = ArrayAudioDriver() if audio else _NullAudioDriver()
        self._session = Session(
            str(TOOLS["swanstation_core"]), str(disc),
            input=self._input, audio=self._audio,
            options=DictOptionDriver(variables=opts),
            path=ExplicitPathDriver(system=str(BIOS.parent if BIOS else TOOLS["bios_dir"]), save=self._tmp.name,
                                    assets=self._tmp.name, playlist=self._tmp.name),
        )
        self.frame = 0

    def __enter__(self):
        self._session.__enter__()
        self.ram = self._session.core.get_memory(libretro.RETRO_MEMORY_SYSTEM_RAM)
        self._ram_mask = len(self.ram) - 1  # 2MB or 8MB, both powers of two
        return self

    def __exit__(self, *exc):
        self._session.__exit__(*exc)
        self._tmp.cleanup()

    # --- running
    def step(self, n=1, p1=0, p2=0):
        """Runs n frames holding the given buttons on each port."""
        self._input.pads = [pad(p1), pad(p2)]
        for _ in range(n):
            self._session.run()
            self.frame += 1

    def run_inputs(self, inputs):
        """inputs: iterable of (p1, p2) per frame."""
        for p1, p2 in inputs:
            self.step(1, p1, p2)

    # --- state
    def save_state(self):
        buf = bytearray(self._session.core.serialize_size())
        assert self._session.core.serialize(buf), "serialize failed"
        return struct.pack("<Q", self.frame) + bytes(buf)

    def load_state(self, blob):
        self.frame = struct.unpack_from("<Q", blob)[0]
        assert self._session.core.unserialize(blob[8:]), "unserialize failed"

    def save_state_file(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_bytes(self.save_state())

    def load_state_file(self, path):
        self.load_state(Path(path).read_bytes())

    # --- memory
    def addr(self, where):
        return SYMBOLS[where] if isinstance(where, str) else where

    def read_bytes(self, where, size, offset=0):
        a = (self.addr(where) + offset) & self._ram_mask
        return bytes(self.ram[a:a + size])

    def read(self, where, fmt="<I", offset=0):
        """Reads a struct-format value (default u32) at a symbol or address, plus offset."""
        return struct.unpack(fmt, self.read_bytes(where, struct.calcsize(fmt), offset))[0]

    def write(self, where, value, fmt="<I", offset=0):
        """Pokes RAM. Harness-only shortcuts (e.g. skipping the prologue); never used in lockstep tests."""
        a = (self.addr(where) + offset) & self._ram_mask
        self.ram[a:a + struct.calcsize(fmt)] = struct.pack(fmt, value)

    def write_bytes(self, where, data, offset=0):
        a = (self.addr(where) + offset) & self._ram_mask
        self.ram[a:a + len(data)] = data

    def entity(self, slot):
        """Address of g_Entities[slot] (Entity is 0xBC bytes; slot 0 is the player)."""
        return SYMBOLS["g_Entities"] + slot * ENTITY_SIZE

    def snapshot(self):
        """The game state tests usually assert on, as plain ints."""
        player = self.entity(0)
        scroll_x, scroll_y = self.read("g_Tilemap", "<h", 0xA), self.read("g_Tilemap", "<h", 0xE)
        x, y = self.read(player, "<h", 2), self.read(player, "<h", 6)  # integer half of 16.16 posX/posY
        return {
            "frame": self.frame,
            "game_state": self.read("g_GameState"),
            "stage": self.read("g_StageId"),
            "room": (self.read("g_Tilemap", "<i", 0x2C), self.read("g_Tilemap", "<i", 0x30)),  # left, top
            "x": x, "y": y, "world_x": scroll_x + x, "world_y": scroll_y + y,
            "hp": self.read(SYMBOLS["g_Status"] + 0x23C, "<i"),
        }

    # --- memory card 1 (libretro save RAM: 128KB, the raw card image)
    def card(self):
        return bytes(self._session.core.get_memory(libretro.RETRO_MEMORY_SAVE_RAM))

    def load_card(self, image):
        mem = self._session.core.get_memory(libretro.RETRO_MEMORY_SAVE_RAM)
        assert len(image) == len(mem), f"card image is {len(image)} bytes, expected {len(mem)}"
        mem[:] = image

    def ram_hash(self):
        import hashlib
        return hashlib.sha1(bytes(self.ram)).hexdigest()

    def take_audio(self):
        """Sound since the last call: interleaved stereo int16 bytes (empty without audio=True)."""
        buf = getattr(self._audio, "_buffer", None)
        if not buf:
            return b""
        data = buf.tobytes()
        del buf[:]
        return data

    # --- video
    def raw_frame(self):
        """(width, height, pixel format, pitch, bytes) of the current frame, straight from the
        video driver's buffer, or None. libretro.py's screenshot() converts pixel by pixel in
        Python (about 18 ms a frame): far too slow for real-time play. Pixel format is the
        libretro one: 0 = 0RGB1555, 1 = XRGB8888, 2 = RGB565 (SwanStation's)."""
        drv = getattr(self._session.video, "_current", None)
        frame, dims = getattr(drv, "_frame", None), getattr(drv, "_frame_dims", None)
        if not frame or not dims or not dims.width:
            return None
        n = dims.pitch * dims.height
        return dims.width, dims.height, int(drv.pixel_format), dims.pitch, memoryview(frame)[:n].tobytes()

    def screenshot(self, path=None):
        """Current frame as a PIL image (saved to path if given)."""
        from PIL import Image
        shot = self._session.video.screenshot()
        if shot is None or not shot.width or not shot.height:  # e.g. mid mode-switch
            return None
        mode = "RGBA" if len(shot.data) == shot.width * shot.height * 4 else "RGB"
        img = Image.frombytes(mode, (shot.width, shot.height), bytes(shot.data)).convert("RGB")
        if path:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            img.save(path)
        return img
