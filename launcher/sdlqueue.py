"""Sound pushed straight to SDL (SDL_QueueAudio), for the Android app (issue 66).

pygame there isn't pygame-ce: its audio callback deadlocks on Python's lock, so the sound went
through SDL_mixer's channel queue. A queued sound only starts when pygame's end-of-sound callback
gets that same lock, and on the Thor it sometimes got it late: the channel went silent with 50 to
180 ms of sound waiting, about once every 3 s. SDL_QueueAudio needs no callback: the main thread
appends each frame's sound, and SDL's own thread plays it.
"""

import ctypes
import glob
import os

AUDIO_S16LSB = 0x8010
SDL_INIT_AUDIO = 0x10


class Spec(ctypes.Structure):
    _fields_ = [("freq", ctypes.c_int), ("format", ctypes.c_uint16), ("channels", ctypes.c_uint8),
                ("silence", ctypes.c_uint8), ("samples", ctypes.c_uint16), ("padding", ctypes.c_uint16),
                ("size", ctypes.c_uint32), ("callback", ctypes.c_void_p), ("userdata", ctypes.c_void_p)]


def load_sdl():
    """The SDL2 library pygame already loaded."""
    names = ["libSDL2.so"]  # Android
    import pygame
    here = os.path.dirname(pygame.__file__)
    names += sorted(glob.glob(os.path.join(here, "..", "pygame*.libs", "libSDL2-2*.so*")))
    names += ["libSDL2-2.0.so.0", "SDL2.dll", "libSDL2.dylib"]
    for name in names:
        try:
            return ctypes.CDLL(name)
        except OSError:
            continue
    raise OSError("no SDL2 library")


class SdlQueue:
    """An SDL audio device, 44.1 kHz stereo 16-bit, fed by push(); queued() is what's waiting."""

    def __init__(self, lib=None):
        self.lib = lib or load_sdl()
        self.lib.SDL_OpenAudioDevice.restype = ctypes.c_uint32
        self.lib.SDL_GetQueuedAudioSize.restype = ctypes.c_uint32
        if self.lib.SDL_InitSubSystem(SDL_INIT_AUDIO) != 0:
            raise OSError("SDL audio didn't start")
        want = Spec(freq=44100, format=AUDIO_S16LSB, channels=2, samples=1024)
        got = Spec()
        import pygame
        if pygame.mixer.get_init():  # SDL_mixer holds the device (Android has only the one)
            pygame.mixer.quit()
        self.dev = self.lib.SDL_OpenAudioDevice(None, 0, ctypes.byref(want), ctypes.byref(got), 0)
        if not self.dev:
            self.lib.SDL_GetError.restype = ctypes.c_char_p
            raise OSError(f"no audio device: {self.lib.SDL_GetError().decode(errors='replace')}")
        self.lib.SDL_PauseAudioDevice(self.dev, 0)

    def push(self, data):
        if data and self.lib.SDL_QueueAudio(self.dev, bytes(data), len(data)) != 0:
            raise OSError("SDL_QueueAudio failed")

    def queued(self):
        return self.lib.SDL_GetQueuedAudioSize(self.dev)

    def clear(self):
        self.lib.SDL_ClearQueuedAudio(self.dev)

    def close(self):
        if self.dev:
            self.lib.SDL_CloseAudioDevice(self.dev)
            self.dev = 0
