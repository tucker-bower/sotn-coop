"""The menus' music and sounds: the game's own, decoded from the player's disc by gamesound.py
into their data folder. Everything here is best effort: no sound device, or no files yet (they're
decoded in the background the first time), and the menus are silent.
"""

import logging
from pathlib import Path

import pygame

log = logging.getLogger("launcher")
NAMES = ("move", "confirm", "back", "error")


class MenuSound:
    def __init__(self, folder, settings):
        self.folder, self.settings = Path(folder), settings
        self.sounds, self.playing, self.loaded = {}, False, False
        self.played = []  # each sound and music change, for tests

    def _load(self):
        if self.loaded:
            return True
        import gamesound
        if not gamesound.ready(self.folder):
            return False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            for name in NAMES:
                path = self.folder / f"{name}.wav"
                if path.exists():
                    self.sounds[name] = pygame.mixer.Sound(str(path))
        except pygame.error:
            log.exception("menu sounds")
        self.loaded = True
        return True

    def volume(self):
        return max(0, min(100, int(self.settings.get("menu_volume", 70)))) / 100

    def play(self, name):
        if not self._load() or name not in self.sounds:
            return
        self.played.append(name)
        try:
            self.sounds[name].set_volume(self.volume())
            self.sounds[name].play()
        except pygame.error:
            pass

    def music(self, on=True):
        """Starts the title music (if it's wanted and isn't playing), or stops it."""
        on = on and self.settings.get("menu_music", True)
        if on == self.playing or (on and not self._load()):
            return
        first, loop = self.folder / "music.wav", self.folder / "music_loop.wav"
        try:
            if on and first.exists():
                pygame.mixer.music.load(str(first))
                pygame.mixer.music.set_volume(self.volume() * 0.8)
                pygame.mixer.music.play()
                if loop.exists():  # after the first time through, from where the game loops it
                    pygame.mixer.music.queue(str(loop), loops=-1)
                self.playing = True
                self.played.append("music")
            elif not on:
                pygame.mixer.music.fadeout(400)
                self.playing = False
                self.played.append("music off")
        except (pygame.error, TypeError):
            log.exception("menu music")
            self.playing = False

    def pause(self, paused):
        """The window lost the keyboard, or has it back."""
        if not self.playing:
            return
        try:
            (pygame.mixer.music.pause if paused else pygame.mixer.music.unpause)()
        except pygame.error:
            pass
