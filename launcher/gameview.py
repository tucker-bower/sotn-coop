"""Both games on screen: the frame loop the player app (app.py) and the dev presets (play.py)
share. Two games, two pads, one window (or two: launcher/display.py), both games' sound with one
game's music, joint saves, savestates at moments worth going back to, and F9 bug reports."""

import collections
import logging
import os
import subprocess
import sys
import threading
import time
from array import array
from pathlib import Path

import pygame

import crashwatch
import report
from display import BAR
from platform_android import ANDROID
from link.mailbox import (BUSY, CONTROL_AGGRO_SHIFT, CONTROL_HOLD, CONTROL_MUTE_MUSIC, CONTROL_NO_AGGRO, CONTROL_PARTNER_VOL_SHIFT, CONTROL_PVP, CUTSCENE, IN_PLAY, scene_speed,
                          ROLE_AUTHORITY, ROLE_GUEST)

STAGE_ST0 = 0x1F  # the prologue
import rules as castle_rules
from winmenu import MENU_EVENT

BACK_KEYS = (pygame.K_ESCAPE, pygame.K_AC_BACK)  # Esc, and Android's Back (pauses, never quits the app)

STUCK_FRAMES = 3600    # a scene with no one moving this long: the status bar says so
ROLLING_EVERY = 300   # frames between the in-memory states an F9 report keeps (never on disk)
GAME_TITLE = 1
REPORT_SECONDS = 60   # inputs and frame times an F9 report keeps
PARTNER_LOST_S = 10


def _not_black(surface):
    """Any of a few dozen pixels lit: the game is showing something."""
    w, h = surface.get_size()
    return any(sum(surface.get_at((x * w // 8, y * h // 6))[:3]) > 24 for x in range(1, 8) for y in range(1, 6))   # online: seconds of silence before telling the player their partner is gone

PAD_BUTTONS = {  # SDL game controller button -> PlayStation button name (harness/emu.py): the defaults
    pygame.CONTROLLER_BUTTON_A: "cross", pygame.CONTROLLER_BUTTON_B: "circle",
    pygame.CONTROLLER_BUTTON_X: "square", pygame.CONTROLLER_BUTTON_Y: "triangle",
    pygame.CONTROLLER_BUTTON_LEFTSHOULDER: "l1", pygame.CONTROLLER_BUTTON_RIGHTSHOULDER: "r1",
    pygame.CONTROLLER_BUTTON_BACK: "select", pygame.CONTROLLER_BUTTON_START: "start",
    pygame.CONTROLLER_BUTTON_DPAD_UP: "up", pygame.CONTROLLER_BUTTON_DPAD_DOWN: "down",
    pygame.CONTROLLER_BUTTON_DPAD_LEFT: "left", pygame.CONTROLLER_BUTTON_DPAD_RIGHT: "right",
}
# Controllers by where a button is, not what's printed on it (issue 250): the bottom face button
# is Cross on an Xbox pad and a Switch pad alike (SDL otherwise swaps A/B and X/Y on Nintendo's)
os.environ.setdefault("SDL_GAMECONTROLLER_USE_BUTTON_LABELS", "0")
# The buttons a player can set (Your settings), in the order shown, with their names
BINDABLE = ("cross", "circle", "square", "triangle", "l1", "r1", "l2", "r2", "start", "select", "up", "down", "left", "right")
BUTTON_LABELS = {"cross": "Cross", "circle": "Circle", "square": "Square", "triangle": "Triangle", "l1": "L1", "r1": "R1",
                 "l2": "L2", "r2": "R2", "start": "Start", "select": "Select", "up": "Up", "down": "Down", "left": "Left",
                 "right": "Right"}
TRIGGERS = {"lefttrigger": pygame.CONTROLLER_AXIS_TRIGGERLEFT, "righttrigger": pygame.CONTROLLER_AXIS_TRIGGERRIGHT}
PAD_NAMES = {  # SDL's names for a controller's buttons (and the triggers, which are axes)
    "a": pygame.CONTROLLER_BUTTON_A, "b": pygame.CONTROLLER_BUTTON_B, "x": pygame.CONTROLLER_BUTTON_X,
    "y": pygame.CONTROLLER_BUTTON_Y, "leftshoulder": pygame.CONTROLLER_BUTTON_LEFTSHOULDER,
    "rightshoulder": pygame.CONTROLLER_BUTTON_RIGHTSHOULDER, "back": pygame.CONTROLLER_BUTTON_BACK,
    "start": pygame.CONTROLLER_BUTTON_START, "leftstick": pygame.CONTROLLER_BUTTON_LEFTSTICK,
    "rightstick": pygame.CONTROLLER_BUTTON_RIGHTSTICK, "dpup": pygame.CONTROLLER_BUTTON_DPAD_UP,
    "dpdown": pygame.CONTROLLER_BUTTON_DPAD_DOWN, "dpleft": pygame.CONTROLLER_BUTTON_DPAD_LEFT,
    "dpright": pygame.CONTROLLER_BUTTON_DPAD_RIGHT}
# How a controller's buttons are shown: by position, as a PlayStation pad's
PAD_SHOWN = {"a": "Bottom", "b": "Right", "x": "Left", "y": "Top", "leftshoulder": "L1", "rightshoulder": "R1",
             "lefttrigger": "L2", "righttrigger": "R2", "back": "Select", "start": "Start", "leftstick": "L3",
             "rightstick": "R3", "dpup": "D-pad up", "dpdown": "D-pad down", "dpleft": "D-pad left", "dpright": "D-pad right"}
DEFAULT_PAD = {"cross": "a", "circle": "b", "square": "x", "triangle": "y", "l1": "leftshoulder", "r1": "rightshoulder",
               "l2": "lefttrigger", "r2": "righttrigger", "start": "start", "select": "back", "up": "dpup",
               "down": "dpdown", "left": "dpleft", "right": "dpright"}
KEYS = [  # per player: key -> button
    {pygame.K_UP: "up", pygame.K_DOWN: "down", pygame.K_LEFT: "left", pygame.K_RIGHT: "right",
     pygame.K_z: "cross", pygame.K_x: "square", pygame.K_c: "circle", pygame.K_v: "triangle",
     pygame.K_a: "l1", pygame.K_s: "r1", pygame.K_d: "l2", pygame.K_w: "r2",
     pygame.K_RETURN: "start", pygame.K_RSHIFT: "select",
     pygame.K_KP8: "rs_up", pygame.K_KP6: "rs_right", pygame.K_KP2: "rs_down", pygame.K_KP4: "rs_left"},
    {pygame.K_i: "up", pygame.K_k: "down", pygame.K_j: "left", pygame.K_l: "right",
     pygame.K_f: "cross", pygame.K_g: "square", pygame.K_h: "circle", pygame.K_t: "triangle",
     pygame.K_q: "l1", pygame.K_e: "r1", pygame.K_r: "l2", pygame.K_y: "r2",
     pygame.K_SPACE: "start", pygame.K_TAB: "select"},
]


def pad_map(overrides=None):
    """A player's controller: PlayStation button -> SDL button name, the defaults with theirs over them."""
    out = dict(DEFAULT_PAD)
    out.update({b: n for b, n in (overrides or {}).items() if b in DEFAULT_PAD and (n in PAD_NAMES or n in TRIGGERS)})
    return out


def key_map(player, overrides=None):
    """A player's keys: key -> PlayStation button. overrides: {button: pygame key name}."""
    out = dict(KEYS[player])
    for button, name in (overrides or {}).items():
        try:
            code = pygame.key.key_code(name)
        except (ValueError, pygame.error):
            continue
        for k in [k for k, b in out.items() if b == button]:
            del out[k]
        out[code] = button
    return out


def bind(overrides, button, value, defaults):
    """overrides with button set to value; a button that had value gets button's old one (a swap)."""
    now = {**defaults, **overrides}
    old = now.get(button)
    out = dict(overrides)
    for other, v in now.items():
        if v == value and other != button:
            out[other] = old
    out[button] = value
    return {b: v for b, v in out.items() if v is not None and defaults.get(b) != v}
FORMATS = {  # libretro pixel format -> (bits per pixel, RGB masks)
    0: (16, (0x7C00, 0x03E0, 0x001F, 0)),       # 0RGB1555
    1: (32, (0xFF0000, 0x00FF00, 0x0000FF, 0)),  # XRGB8888
    2: (16, (0xF800, 0x07E0, 0x001F, 0)),       # RGB565
}


KNEE = 24576  # above this the mix is compressed 4:1 instead of clipped


def mix(sounds, solo=None):
    """Both games' sound (16-bit stereo) mixed into one stream. Only one game plays music in play
    (CONTROL_MUTE_MUSIC), so the sum is mostly sound effects. solo: that game's sound alone, for
    when both games are making the same sound (the title, the intro, the prologue, the same
    cutscene): the two copies summed clipped hard (playtest 2026-10-20: buzzing and crackling)."""
    if solo is not None and solo < len(sounds) and sounds[solo]:
        return sounds[solo]
    sounds = [x for x in sounds if x]
    if len(sounds) < 2:
        return sounds[0] if sounds else b""
    a, b = array("h", sounds[0][:len(sounds[0]) // 2 * 2]), array("h", sounds[1][:len(sounds[1]) // 2 * 2])
    if len(a) < len(b):
        a, b = b, a
    for i, v in enumerate(b):
        v += a[i]
        if v > KNEE:
            v = min(32767, KNEE + (v - KNEE) // 4)
        elif v < -KNEE:
            v = max(-32768, -KNEE + (v + KNEE) // 4)
        a[i] = v
    return a.tobytes()


def same_sound(pa, pb):
    """Both games make the same sound: neither is in play in the castle (title, intro video,
    prologue, menus), or both run the same cutscene."""
    in_castle = [q.flags & IN_PLAY and q.stage != STAGE_ST0 for q in (pa, pb)]
    if not any(in_castle):
        return True
    return bool(pa.flags & pb.flags & CUTSCENE) and pa.stage == pb.stage and pa.room == pb.room


PRIMED_BYTES = 44100 * 4 // 20  # 50 ms: what the device waits for, after running dry


class Pacer:
    """60 frames a second, to the deadline: pygame's Clock.tick(60) waits whole milliseconds, so
    Android's pygame ran 16 ms frames, 62.5 a second, and the games 4% fast (issue 66). Behind by
    more than 0.1 s (a load, a box), it starts again from now rather than racing to catch up."""

    def __init__(self, fps=60):
        self.period, self.next = 1 / fps, None

    def wait(self):
        now = time.perf_counter()
        if self.next is None or now - self.next > 0.1:
            self.next = now
        self.next += self.period
        if self.next > now:
            time.sleep(self.next - now)


class Audio:
    """The games' sound, through an SDL audio device fed from a small buffer."""

    def __init__(self):
        from pygame._sdl2 import audio as sdl_audio
        self.buf, self.lock = bytearray(), threading.Lock()
        self.underruns = self.short_bytes = self.dropped_bytes = self.pulls = 0  # F9 reports, tests
        self.pushes = self.clipped = 0  # frames of sound, and those that hit full scale
        self.fed_bytes, self.started = 0, time.monotonic()  # sound handed to the device, since when (issue 66)
        self.pushed_at, self.push_gap, self.gaps = 0.0, 0.0, collections.deque(maxlen=30)  # each underrun: when, since the last push, buffered
        self.dev = self.chan = self.queue = None
        self.primed = False
        if not getattr(pygame, "IS_CE", False):
            try:  # pygame (not -ce): Android, design/M9. Straight to SDL (issue 66)
                from sdlqueue import SdlQueue
                self.queue = SdlQueue()
                return
            except Exception:  # noqa: BLE001  (then SDL_mixer, as before)
                logging.getLogger(__name__).exception("SDL audio queue")
            # pygame (not -ce: Android, design/M9): its AudioDevice's Python callback deadlocks on
            # the GIL there, so the sound goes through SDL_mixer, queued from the main thread.
            if pygame.mixer.get_init() != (44100, -16, 2):
                pygame.mixer.quit()
                pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=1024)
            self.chan = pygame.mixer.Channel(0)
            self.fed_at = 0.0
            return
        kw = dict(iscapture=False, frequency=44100, audioformat=sdl_audio.AUDIO_S16, numchannels=2,
                  chunksize=1024, allowed_changes=0, callback=self._pull)
        self.dev = sdl_audio.AudioDevice(devicename=None, **kw)  # the default output
        self.dev.pause(0)

    def _feed(self):
        """SDL_mixer: one sound playing and one queued behind it, each all the sound buffered when
        it's made (a frame or more). After running dry it waits for about 50 ms of sound first,
        so a slow frame costs one short gap, not a crackle. A channel that stops taking sound
        (seen on an emulator: idle, or stuck with one queued) is restarted."""
        frame = 44100 * 4 // 60
        now = time.monotonic()
        with self.lock:
            busy = self.chan.get_busy()
            stuck = busy and now - self.fed_at > 0.5  # nothing taken for longer than a queue lasts
            if stuck:
                self.chan.stop()
                busy = False
            if busy and (self.chan.get_queue() is not None or len(self.buf) < frame):
                return
            if not busy and len(self.buf) < 3 * frame:
                return
            n = len(self.buf) // 4 * 4  # whole stereo samples
            sound = pygame.mixer.Sound(buffer=bytes(self.buf[:n]))
            del self.buf[:n]
            self.fed_bytes += n
            self.pulls += 1
            self.fed_at = now
            if busy:
                self.chan.queue(sound)
            else:
                if self.pulls > 1:  # it ran dry (the first start isn't)
                    self.underruns += 1
                    self.gaps.append((round(now - self.started, 2), round(self.push_gap, 3), n // 4))
                self.chan.play(sound)

    def _queue(self):
        """SDL_QueueAudio (issue 66): everything buffered goes to SDL. After running dry it waits
        for 50 ms of sound first, as _pull does; over 0.2 s waiting in SDL, the newest is dropped."""
        waiting = self.queue.queued()
        if self.primed and waiting == 0:
            self.underruns += 1
            self.gaps.append((round(time.monotonic() - self.started, 2), round(self.push_gap, 3), len(self.buf) // 4))
            self.primed = False
        if not self.primed and len(self.buf) < PRIMED_BYTES:
            return
        self.primed = True
        n = len(self.buf) // 4 * 4
        if waiting + n > 44100 * 4 // 5:
            self.dropped_bytes += n
        else:
            self.queue.push(self.buf[:n])
            self.fed_bytes += n
            self.pulls += 1
        del self.buf[:n]

    def close(self):
        if self.queue is not None:
            self.queue.close()
        if self.dev is not None:
            self.dev.close()
        elif self.chan is not None:
            self.chan.stop()

    def _pull(self, dev, mem):
        """After running dry it waits for 50 ms of sound first, as _feed does: otherwise each pull
        comes up a little short, and a slow frame becomes a crackle (issue 134)."""
        with self.lock:
            self.pulls += 1
            self.primed = self.primed or len(self.buf) >= PRIMED_BYTES
            n = min(len(mem), len(self.buf)) if self.primed else 0
            mem[:n] = self.buf[:n]
            del self.buf[:n]
            self.fed_bytes += n
            if n < len(mem):
                self.underruns += self.primed
                self.short_bytes += len(mem) - n
                self.primed = False
        for i in range(n, len(mem)):
            mem[i] = 0

    def push(self, data):
        if data:
            x = array("h", data[:len(data) // 2 * 2])
            self.pushes += 1
            now = time.monotonic()
            self.push_gap, self.pushed_at = now - self.pushed_at, now
            self.clipped += max(x) >= 32767 or min(x) <= -32768
        with self.lock:
            self.buf += data
            if len(self.buf) > 44100 * 4 // 5:  # over 0.2 s behind: drop the oldest
                self.dropped_bytes += len(self.buf) - 44100 * 4 // 10
                del self.buf[:len(self.buf) - 44100 * 4 // 10]
        if self.queue is not None:
            with self.lock:
                self._queue()
        elif self.chan is not None:
            self._feed()

    def clear(self):
        with self.lock:
            self.buf.clear()
            if self.queue is not None:
                self.queue.clear()
                self.primed = False

    def forget_wait(self, stats):
        """The games stood still in the note box: what the sound did meanwhile isn't an underrun."""
        self.pulls, self.underruns = stats["pulls"], stats["underruns"]
        self.short_bytes = round(stats["short_ms"] * 176.4)

    def stats(self):
        return {"pushes": self.pushes, "clipped": self.clipped, "pulls": self.pulls, "underruns": self.underruns, "short_ms": round(self.short_bytes / 176.4),
                "dropped_ms": round(self.dropped_bytes / 176.4), "fed_ms": round(self.fed_bytes / 176.4),
                "seconds": round(time.monotonic() - self.started, 1),
                "path": "sdl queue" if self.queue is not None else "mixer" if self.chan is not None else "callback",
                "mixer": pygame.mixer.get_init() if self.chan is not None else None, "gaps": list(self.gaps)}


def frame_surface(surf, fmt, pitch, height):
    """A surface the core's raw frame bytes can be written into as they are."""
    bits, masks = FORMATS[fmt]
    width = pitch * 8 // bits
    if surf is None or surf.get_size() != (width, height) or surf.get_bitsize() != bits:
        surf = pygame.Surface((width, height), 0, bits, masks)
    return surf


class Pads:
    """Controllers and the keyboard, as each player's pad. assign: each player's controller
    (instance id), "kb" (keyboard only), or None ("the Nth controller")."""

    def __init__(self, assign=(None, None)):
        from pygame._sdl2 import controller as sdl_controller
        self.sdl = sdl_controller
        sdl_controller.init()
        self.assign = list(assign)
        self.virtual = {}  # tests (launcher/uxdriver.py): instance id -> {name, pressed buttons}
        self.pad_maps = [pad_map(), pad_map()]  # each player's buttons (Your settings: issue 250)
        self.key_maps = [dict(KEYS[0]), dict(KEYS[1])]
        self.refresh()

    def set_buttons(self, player, pad=None, keys=None):
        """A player's own buttons: {PlayStation button: SDL button name} and {button: key name}."""
        self.pad_maps[player] = pad_map(pad)
        self.key_maps[player] = key_map(player, keys)

    def refresh(self):
        """The plugged-in controllers, as {instance id: Controller}. (Controller.as_joystick()
        fails on some Windows setups, so ids come from the joystick of the same device index.)"""
        self.by_id = {}
        pygame.joystick.init()
        for i in range(self.sdl.get_count()):
            try:
                if self.sdl.is_controller(i):
                    self.by_id[pygame.joystick.Joystick(i).get_instance_id()] = self.sdl.Controller(i)
            except pygame.error:
                continue
        self.controllers = list(self.by_id.values())

    def name(self, iid):
        if iid in self.virtual:
            return self.virtual[iid]["name"]
        c = self.by_id.get(iid)
        return c.name if c else "Controller"

    def names(self):
        return [c.name for c in self.controllers] + [v["name"] for v in self.virtual.values()]

    def controller(self, player):
        want = self.assign[player] if player < len(self.assign) else None
        if want == "kb":
            return None
        if want is not None:
            return self.by_id.get(want)
        return self.controllers[player] if player < len(self.controllers) else None

    def missing(self, player):
        """The player's assigned controller isn't plugged in (any more)."""
        want = self.assign[player] if player < len(self.assign) else None
        return want not in (None, "kb") and want not in self.virtual and self.controller(player) is None

    def mask(self, player, keys):
        pressed = set()
        c = self.controller(player)
        if c is not None:
            for name, btn in self.pad_maps[player].items():
                if btn in TRIGGERS:
                    if c.get_axis(TRIGGERS[btn]) > 16000:
                        pressed.add(name)
                elif c.get_button(PAD_NAMES[btn]):
                    pressed.add(name)
            x, y = c.get_axis(pygame.CONTROLLER_AXIS_LEFTX), c.get_axis(pygame.CONTROLLER_AXIS_LEFTY)
            pressed |= {n for n, on in (("left", x < -16000), ("right", x > 16000), ("up", y < -16000),
                                        ("down", y > 16000)) if on}
            # The right stick (Alucard's spell shortcuts: design/M8b §3.2), as the game's padExtra.
            x, y = c.get_axis(pygame.CONTROLLER_AXIS_RIGHTX), c.get_axis(pygame.CONTROLLER_AXIS_RIGHTY)
            pressed |= {n for n, on in (("rs_left", x < -20000), ("rs_right", x > 20000), ("rs_up", y < -20000),
                                        ("rs_down", y > 20000)) if on}
        want = self.assign[player] if player < len(self.assign) else None
        if want in self.virtual:
            pressed |= self.virtual[want]["pressed"]
        pressed |= {name for key, name in self.key_maps[player].items() if keys[key]}
        return "+".join(sorted(pressed))


def partner_crashed(session):
    return bool(session.joint and session.joint.partner_crashed)


class GameView:
    """Runs the games in the window until the player leaves (Esc: the pause menu)."""

    def __init__(self, session, display, pads, audio, playthrough=None, goal="", music="auto", rules=None,
                 save_cards=None, frames=0, profile=False, launcher=None, partner_vol=60, rush=None, joiner=False,
                 script=()):
        self.s, self.display, self.pads, self.audio = session, display, pads, audio
        self.launcher = launcher
        self.games = tuple(session.games)
        self.online = len(self.games) == 1
        self.script = [pad for frames, pad in script for _ in range(frames)]  # played from the title on
        self.scene_speed = 1
        self.script_on = False
        self.playthrough, self.goal = playthrough, goal
        self.rush = rush  # bossrush.BossRush: ticked every frame, its line on the status bar
        self.music_mode, self.music = music, None
        self.solo = 0  # couch: play one game's sound while both make the same (see same_sound)
        self.partner_vol = partner_vol
        self.joiner = joiner  # online, in the host's castle: its rules are the host's
        self.set_rules(rules)
        self.save_cards = save_cards  # (path A, path B) or (path local,)
        self.frames, self.profile = frames, profile
        self.canvas = display.canvas
        self.font = pygame.font.SysFont("consolas", 16)
        self.big = pygame.font.SysFont("georgia", 28)
        self.journal = report.Journal()
        self.still = {}
        self.inputs = collections.deque(maxlen=60 * REPORT_SECONDS)
        self.watch = crashwatch.CrashWatch()
        self.frame_times = collections.deque(maxlen=60 * REPORT_SECONDS)
        self.notice, self.notice_until = "", 0
        self.mismatch = None
        self.moments = None
        self.netsim = None
        if playthrough:
            from archive import Moments
            self.moments = Moments(playthrough)
        if not self.online and launcher and launcher.settings.get("netsim"):
            self.set_netsim(launcher.settings["netsim"])

    frame = 0

    def say(self, text, frames=300):
        self.notice, self.notice_until = text, self.frame + frames

    def set_rules(self, rules):
        """The castle's rules (launcher/rules.py), at the start and whenever they change: in the
        games, and, from the host, on to the partner."""
        self.rules = castle_rules.clean(rules)
        chance = max(0, min(255, round(self.rules["aggro"] * 256 / 100)))
        control = CONTROL_NO_AGGRO if chance == 0 else chance << CONTROL_AGGRO_SHIFT
        # the partner's sounds, % of their volume (M13: module/partner.c; 0 would mean the default)
        control |= max(1, min(100, int(self.partner_vol))) << CONTROL_PARTNER_VOL_SHIFT
        if self.rules["pvp"]:  # M15: the partner's attacks hurt
            control |= CONTROL_PVP
        self.aggro = control
        self.music = None  # couch: the control word is written again, with the music's bit
        words = castle_rules.encode(self.rules)
        for g in self.games:
            g.host("set_rules", words, None if self.joiner else self.rules)
        if self.s.joint:
            self.s.joint.shared_level = self.rules["shared_level"]

    def follow_host(self):
        """A joiner: the host changed the castle's rules. They go on the joiner's copy too."""
        theirs = (self.games[0].host("status").get("partner_hello") or {}).get("rules")
        if theirs is None or castle_rules.clean(theirs) == self.rules:
            return
        self.set_rules(theirs)
        if self.playthrough:
            self.playthrough.set_rules(self.rules)
        self.say("Your partner changed the castle's rules", 300)

    def moment(self, event, where=""):
        if self.playthrough:
            self.playthrough.savestate(event, self.games, where)
            self.playthrough.save_info()

    def set_netsim(self, profile):
        """Couch, for testing: both games through a simulated internet (Help ▸ Developer)."""
        if self.online:
            return
        self.s.set_net(profile)
        self.netsim = profile

    # --- overlays: drawn on the canvas, over the paused games

    def overlay(self, title, lines, items=(), sel=0, box_text=None, box_caret=None):
        c = self.canvas
        c.fill((0, 0, 0, 175))
        cx = c.get_width() // 2
        t = self.big.render(title, True, (220, 200, 160))
        c.blit(t, (cx - t.get_width() // 2, 110))
        for k, line in enumerate(lines):
            t = self.font.render(line, True, (220, 220, 220))
            c.blit(t, (cx - t.get_width() // 2, 160 + k * 24))
        y = 170 + len(lines) * 24
        rects = []
        for k, text in enumerate(items):
            color = (255, 230, 150) if k == sel else (180, 180, 180)
            t = self.big.render(("› " if k == sel else "  ") + text, True, color)
            c.blit(t, (cx - 240, y + k * 44))
            rects.append(pygame.Rect(cx - 240, y + k * 44, 480, 40))
        if box_text is not None:
            box = pygame.Rect(80, y, c.get_width() - 160, 40)
            pygame.draw.rect(c, (30, 30, 40), box)
            pygame.draw.rect(c, (220, 200, 160), box, 1)
            c.blit(self.font.render(box_text, True, (240, 240, 240)), (box.x + 8, box.y + 11))
            if box_caret is not None:
                from ui.textline import draw_caret
                draw_caret(c, box.x + 8 + self.font.size(box_text[:box_caret])[0], box.y + 9,
                           self.font.get_height() + 4, (240, 240, 240))
        self.display.present(over_games=True)
        return rects

    def scripted(self, pads):
        """The game's title menus, played through; nobody's buttons count until they're done."""
        if any(g.read("g_GameState") != GAME_TITLE for g in self.games) and not self.script_on:
            return [""] * len(pads)
        self.script_on = True
        pad = self.script.pop(0)
        return [pad] * len(pads)

    def scene_speed_now(self):
        if not self.online:
            return scene_speed([g.mailbox("self_presence") for g in self.games], False)
        g = self.games[0]
        linked = g.mailbox("partner_age") <= 30
        return scene_speed([g.mailbox("self_presence")] + ([g.mailbox("partner_presence")] if linked else []), not linked)

    def keep_playing(self):
        """While a box is up: online, this game runs on with no buttons held, or the partner's game
        would lose it (playtest 0.14: reporting a problem froze the partner). On the couch both wait."""
        if self.online:
            for g in self.games:
                g.frame_start(0)
            for g in self.games:
                g.frame_end()
            self.frame += 1
            if self.audio:
                self.audio.clear()

    def ask_note(self):
        """"What happened?" Typed text, or "" (Enter on nothing, or Esc)."""
        from ui.textline import TextLine, typing
        line = TextLine("", 300)
        with typing():
            while True:
                for ev in pygame.event.get():
                    if self.display.handle(ev):
                        continue
                    if ev.type in (pygame.QUIT, pygame.WINDOWCLOSE):
                        return line.text
                    if line.handle(ev):
                        continue
                    if ev.type == pygame.KEYDOWN:
                        if ev.key == pygame.K_RETURN:
                            return line.text
                        if ev.key in BACK_KEYS:
                            return ""
                    elif ev.type == pygame.CONTROLLERBUTTONDOWN and ev.button in (pygame.CONTROLLER_BUTTON_A,
                                                                                    pygame.CONTROLLER_BUTTON_START):
                        return line.text
                shown, at = line.window(80)
                self.overlay("Report a problem: what happened? (optional)",
                             ["Type, then Enter to save the report (or press Cross / A: no note). Esc: no note."],
                             box_text=shown, box_caret=at)
                self.keep_playing()
                pygame.time.wait(16)

    def open_crash_window(self, path):
        """Android has one window: the same questions, on its screen. Elsewhere, a process of its
        own (crash_window.py), asking the player before anything is sent."""
        if ANDROID:
            note = self.ask_note()
            if report.can_send() and self.ask_send():
                self.send_report(path, note)
            return
        app = [sys.executable] if getattr(sys, "frozen", False) else [sys.executable, str(Path(__file__).with_name("app.py"))]
        subprocess.Popen(app + ["--crash-window", str(path)])

    def crashed(self, why):
        """A game crashed or hung: its report first, while the rolling states still show it
        happening, then the partner, then the window. Back to the menu: this game is lost."""
        logging.getLogger("launcher").error("%s", why)
        live = [g for g in self.games if getattr(g, "proc", None) is None or g.proc.is_alive()]
        path = None
        try:
            path = self.report(note=f"Automatic report: {why}.", games=live)
        except Exception:  # noqa: BLE001 - the player still has to be told
            logging.getLogger("launcher").exception("crash report")
        if self.online and self.s.joint and live:
            try:
                self.s.joint.host.send_control({"op": "crashed"})
            except Exception:  # noqa: BLE001 - nothing more to tell it with
                logging.getLogger("launcher").exception("telling the partner")
        if path:
            self.open_crash_window(path)
        self.say("The game stopped, so it's going back to the menu.", 180)
        return "menu"

    def report(self, note=None, games=None):
        games = self.games if games is None else games
        shot = self.display.screenshot()  # the window as it was: the games, not the note box
        shot.fill((0, 0, 0), (0, shot.get_height() - BAR, shot.get_width(), BAR))  # it can show a path
        taken = report.snapshot(games, self.audio)
        interactive = note is None
        held = interactive and self.online
        if held:  # online the game runs on behind the boxes (keep_playing), held still (#192)
            self.games[0].mailbox("set_control", self.aggro | CONTROL_HOLD)
        try:
            return self._report(games, shot, taken, note, interactive)
        finally:
            if held:
                self.games[0].mailbox("set_control", self.aggro)

    def _report(self, games, shot, taken, note, interactive):
        if interactive:
            note = self.ask_note()
        kept = zip(*(g.kept_states() for g in games))  # the same frames in each game
        rolling = [(states[0][0], *(st for _, st in states)) for states in kept]
        path = report.write(games, self.playthrough, shot, rolling, self.inputs,
                            self.frame_times, self.pads.names(), note, extra={"solo": self.solo, "rules": self.rules},
                            taken=taken, journal=self.journal)
        if self.audio:
            self.audio.forget_wait(taken["audio"])
        if not interactive:
            self.say(f"Bug report saved: {path.name} (in {path.parent})", 480)
        elif not report.can_send():
            self.say(f"Bug report saved in {path.parent}. Please email it to {report.REPORT_EMAIL}", 600)
        elif self.ask_send():
            self.send_report(path, note)
        else:
            self.say(f"Bug report kept: {path.name} (in {path.parent})", 480)
        return path

    def ask_send(self):
        """Send the report, or keep it here?"""
        while True:
            for ev in pygame.event.get():
                if self.display.handle(ev):
                    continue
                if ev.type in (pygame.QUIT, pygame.WINDOWCLOSE):
                    return False
                if ev.type == pygame.KEYDOWN and ev.key == pygame.K_RETURN:
                    return True
                if ev.type == pygame.KEYDOWN and ev.key in BACK_KEYS:
                    return False
                if ev.type == pygame.CONTROLLERBUTTONDOWN and ev.button == pygame.CONTROLLER_BUTTON_A:
                    return True
                if ev.type == pygame.CONTROLLERBUTTONDOWN and ev.button == pygame.CONTROLLER_BUTTON_B:
                    return False
            self.overlay("Send this report?",
                         ["It emails your note, screenshots, inputs, logs, game state and memory cards to the",
                          "SOTN Co-op team. Your folders, disc path, typed name and IP address are removed.",
                          "Enter / Cross: send.   Esc / Circle: keep it on this device."])
            self.keep_playing()
            pygame.time.wait(16)

    def send_report(self, path, note):
        """In the background: the games carry on, and online the partner never waits."""
        self.say("Sending the bug report...", 3600)

        def run():
            error = report.send(path, note)
            self.say(f"Couldn't send the bug report: {error}. It's in {path.parent}" if error
                     else "Bug report sent. Thank you!", 480)
        threading.Thread(target=run, daemon=True).start()

    def write_cards(self):
        if self.save_cards:
            for g, path in zip(self.games, self.save_cards):
                path.write_bytes(g.card())

    def menu_action(self, action):
        """A menu-bar item, in a game. Returns what run() should do: None, "pause", "report",
        "menu", "quit" or ("navigate", action)."""
        if action == "pause":
            return "pause"
        if action == "report":
            return "report"
        if action == "moment":  # a savestate of the castle, any time, for the Savestates menu
            self.moment("Saved", "")
            self.say("Savestate saved", 180)
            return None
        if action == "leave":
            return "menu"
        if action == "quit":
            return "quit"
        if action.startswith("netsim:"):
            if self.launcher:
                self.launcher.action(action)
            self.set_netsim(None if action.endswith("off") else action.split(":", 1)[1])
            self.say(f"Simulated network: {self.netsim or 'off'}", 240)
            return None
        if self.launcher and self.launcher.action(action) is not False:
            return None  # View, Help...: done where it stands
        return ("navigate", action)  # New game, Savestates...: leave the game first

    def pause_menu(self, why=None):
        """Esc (or Start on a TV, with the menu bar out of reach): Resume, the View settings, How to
        play, Report a problem, Leave. Returns "resume", "menu", "quit" or ("navigate", action)."""
        from display import LAYOUT_NAMES
        sel = 0
        if self.audio:
            self.audio.clear()
        st = self.launcher.settings if self.launcher else self.display.settings
        while True:
            items = ["Resume",
                     f"Couch co-op layout: {LAYOUT_NAMES.get(st.get('layout', 'auto'), 'Automatic')}",
                     "How to play", "Castle rules", "Your settings", "Report a problem (F9)", "Save and go back to the menu"]
            for ev in pygame.event.get():
                if self.display.handle(ev):
                    continue
                if ev.type in (pygame.QUIT, pygame.WINDOWCLOSE):
                    return "quit"
                if ev.type == MENU_EVENT:
                    r = self.menu_action(ev.action)
                    if r == "report":
                        self.report()
                        return "resume"
                    if r not in (None, "pause"):
                        return r
                    continue
                move = None
                if ev.type == pygame.KEYDOWN:
                    move = {pygame.K_UP: -1, pygame.K_DOWN: 1}.get(ev.key)
                    if ev.key in BACK_KEYS:
                        return "resume"
                    if ev.key in (pygame.K_RETURN, pygame.K_z):
                        move = "ok"
                elif ev.type == pygame.CONTROLLERBUTTONDOWN:
                    move = {pygame.CONTROLLER_BUTTON_DPAD_UP: -1, pygame.CONTROLLER_BUTTON_DPAD_DOWN: 1,
                            pygame.CONTROLLER_BUTTON_A: "ok", pygame.CONTROLLER_BUTTON_B: "back"}.get(ev.button)
                elif ev.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
                    pos = self.display.to_canvas(ev.pos)
                    for k, r in enumerate(getattr(self, "_rects", [])):
                        if pos and r.collidepoint(pos):
                            sel = k
                            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                                move = "ok"
                if move == "back":
                    return "resume"
                if move == "ok":
                    if sel == 0:
                        return "resume"
                    if sel == 1:  # cycle the layout, as View in the menu bar
                        key, order = "layout", list(LAYOUT_NAMES)
                        now = st.get(key, order[0])
                        st[key] = order[(order.index(now) + 1) % len(order)] if now in order else order[0]
                        if self.launcher:
                            self.launcher.action(f"{key}:{st[key]}")
                        continue
                    if sel == 2:
                        if self.launcher:
                            self.launcher.action("help_play")
                        continue
                    if sel == 3:
                        if self.launcher:
                            self.launcher.action("rules")
                        continue
                    if sel == 4:  # each player's own: apart from the castle's rules (issue 232)
                        if self.launcher:
                            self.launcher.action("player_settings")
                        continue
                    if sel == 5:
                        self.report()
                        return "resume"
                    return "menu"
                if isinstance(move, int):
                    sel = (sel + move) % len(items)
            lines = [why] if why else []
            self._rects = self.overlay("Paused", lines, items, sel)
            pygame.time.wait(16)

    def partner_gone(self):
        """Online: what to tell the player, once, when the partner leaves or goes silent
        (playtest 2026-10-25: closing one app left the other saying nothing)."""
        state = getattr(self, "partner_state", None)
        if state == getattr(self, "_told", None):
            return None
        self._told = state if state in ("left", "lost", "crashed") else None
        if state == "crashed":
            return "Your partner's game stopped. You can keep playing alone."
        if state == "left":
            return "Your partner left the game. You can keep playing alone."
        if state == "lost":
            return (f"Lost contact with your partner (nothing for {PARTNER_LOST_S} s). Keep playing: "
                    "they come back if the connection does.")
        return None

    def wait_for_controller(self, player):
        """A player's controller was unplugged: that game waits until any controller's button is
        pressed (it becomes that player's), or Esc."""
        if self.audio:
            self.audio.clear()
        while True:
            for ev in pygame.event.get():
                if self.display.handle(ev):
                    continue
                if ev.type in (pygame.QUIT, pygame.WINDOWCLOSE):
                    return "quit"
                if ev.type == pygame.CONTROLLERDEVICEADDED:
                    self.pads.refresh()
                elif ev.type == pygame.CONTROLLERBUTTONDOWN and ev.instance_id not in self.pads.assign:
                    self.pads.assign[player] = ev.instance_id
                    self.pads.refresh()
                    return "resume"
                elif ev.type == pygame.KEYDOWN and ev.key in BACK_KEYS:
                    r = self.pause_menu(f"Player {player + 1}: controller disconnected.")
                    if r != "resume":
                        return r
            self.overlay(f"Player {player + 1}: controller disconnected",
                         ["Plug it back in and press any button on it (or on another controller).",
                          "Esc: the pause menu."])
            pygame.time.wait(16)

    def status_line(self, clock):
        s = self.s
        fps = f"{clock.get_fps():.0f} fps"
        if getattr(s, "solo", False):  # no partner to report on (design/M11)
            return f"Solo   ·   F9: report a problem   ·   Esc: pause   ·   {fps}", (self.games[0].mailbox("self_presence"),)
        if self.online:
            g = self.games[0]
            hst = g.host("status")
            self.mismatch = hst.get("mismatch")
            age = g.mailbox("partner_age")
            pa, pb = g.mailbox("self_presence"), g.mailbox("partner_presence")
            together = age <= 30 and {pa.role, pb.role} == {ROLE_AUTHORITY, ROLE_GUEST}
            self.partner_state = ("crashed" if partner_crashed(self.s) else
                                  "left" if hst.get("partner_left") else
                                  "lost" if hst.get("partner_hello") and (hst.get("rx_age") or 0) > PARTNER_LOST_S
                                  else "here" if age <= 30 else getattr(self, "partner_state", None))
            if self.mismatch:
                link = self.mismatch
            elif self.partner_state == "left":
                link = "Your partner left the game"
            elif age > 180:
                link = "Waiting for your partner…"
            else:
                rtt, loss = hst.get("rtt_ms"), hst.get("loss_pct")
                word = "" if rtt is None else (" (good)" if rtt < 150 else " (ok)" if rtt < 300 else " (laggy)")
                link = f"Partner connected · ping {rtt if rtt is not None else '?'} ms{word}"
                if loss:
                    link += f" · {loss:.0f}% lost"
            return (f"{link}   ·   {'Together' if together else 'Apart'}   ·   F9: report a problem   ·   "
                    f"Esc: pause   ·   {fps}"), (pa, pb) if age <= 30 else (pa,)
        pa, pb = s.a.mailbox("self_presence"), s.b.mailbox("self_presence")
        together = {pa.role, pb.role} == {ROLE_AUTHORITY, ROLE_GUEST}
        sim = f"   ·   simulated network: {self.netsim}" if self.netsim else ""
        return (f"{'Together' if together else 'Apart'}   ·   music: {'left' if self.music == 0 else 'right'} "
                f"({self.music_mode}, F1)   ·   F9: report a problem   ·   Esc: pause   ·   {fps}{sim}"), (pa, pb)

    def ping_text(self):
        st = self.launcher.settings if self.launcher else {}
        if not (self.online and st.get("show_ping")):
            return None
        rtt = self.games[0].host("status").get("rtt_ms")
        return f"{rtt} ms" if rtt is not None else "… ms"

    def stuck_note(self, presences):
        """Says so if a player has stood still in a scene for a long time."""
        for i, p in enumerate(presences):
            state = (p.stage, p.room_left, p.room_top, p.x, p.y)
            if not p.flags & (BUSY | CUTSCENE) or state != self.still.get(i, (None, 0))[0]:
                self.still[i] = (state, self.frame)
            elif self.frame - self.still[i][1] > STUCK_FRAMES:
                who = "Your partner" if self.online and i else f"Player {i + 1}"
                return f"{who} seems stuck in a scene. Esc: pause, to quit and Continue"
        return None

    started = False  # a picture has come from the game (before that, its boot's black screen)

    def run(self):
        """Returns when the player goes back to the menu (or closes the window): "menu", "quit"
        or ("navigate", action)."""
        s = self.s
        clock, pacer, self.frame, last_cards = pygame.time.Clock(), Pacer(), 0, time.time()
        status, raw, prof = "", [None, None], []
        result = "menu"
        while True:
            leave = None
            for ev in pygame.event.get():
                if self.display.handle(ev):
                    continue
                todo = None
                if ev.type in (pygame.QUIT, pygame.WINDOWCLOSE):
                    leave = "quit"
                elif ev.type == MENU_EVENT:
                    todo = self.menu_action(ev.action)
                elif ev.type == pygame.KEYDOWN and ev.key in BACK_KEYS:
                    todo = "pause"
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F1:
                    self.music_mode = {"auto": "left", "left": "right", "right": "auto"}[self.music_mode]
                    self.music = None
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F9:
                    todo = "report"
                elif ev.type in (pygame.CONTROLLERDEVICEADDED, pygame.CONTROLLERDEVICEREMOVED):
                    self.pads.refresh()
                if todo == "pause":
                    todo = self.pause_menu()
                    todo = None if todo == "resume" else todo
                elif todo == "report":
                    self.report()
                    todo = None
                if todo:
                    leave = todo
            for player in range(len(self.games)):
                if not leave and self.pads.missing(player):
                    r = self.wait_for_controller(player)
                    leave = None if r == "resume" else r
            gone = self.partner_gone()
            if not leave and gone:
                r = self.pause_menu(gone)
                leave = None if r == "resume" else r
            if leave:
                result = leave
                break
            keys = pygame.key.get_pressed()
            t0 = time.perf_counter()
            pads = [castle_rules.remapped(self.pads.mask(i, keys), self.rules) for i in range(len(self.games))]
            if self.script:
                pads = self.scripted(pads)
            self.inputs.append((self.frame, *pads))
            if self.frame % ROLLING_EVERY == 0:
                for g in self.games:
                    g.keep_state(self.frame)
            try:
                for k in range(self.scene_speed - 1):  # a scene both players asked to skip: no sound or picture
                    for g in self.games:
                        g.frame_start(0)
                    for g in self.games:
                        g.frame_end()
                    self.frame += 1
                for g, pad in zip(self.games, pads):  # both games run their frame at the same time
                    g.frame_start(pad)
                replies = [g.frame_end() for g in self.games]
            except (EOFError, OSError):  # a worker process died
                result = self.crashed("a game's process ended")
                break
            t1 = time.perf_counter()
            frames = []
            for i, (g, (picture, sound)) in enumerate(zip(self.games, replies)):
                if picture:
                    w, h, fmt, pitch, n = picture
                    raw[i] = frame_surface(raw[i], fmt, pitch, h)
                    # Through shared memory from a worker process; an in-process game (Android)
                    # hands the bytes over as they are.
                    raw[i].get_buffer().write(bytes(g.shm.buf[:n]) if g.shm is not None else n, 0)
                    frames.append(raw[i].subsurface((0, 0, w, h)))
                else:
                    frames.append(None)
            if self.audio:
                self.audio.push(mix([sound for _, sound in replies], self.solo))
            self.frame += 1
            if self.frame % crashwatch.EVERY == 0:
                why = self.watch.check(self.games)
                if why:
                    result = self.crashed(why)
                    break
            if s.joint and (self.online or self.frame % 15 == 0):  # online ticks every frame for save messages
                s.joint.tick()
            if self.rush:
                self.rush.tick()
            if self.joiner and self.frame % 60 == 0:
                self.follow_host()
            if self.frame % 15 == 0:
                if self.online:
                    self.games[0].mailbox("set_control", self.aggro)  # online: never mute local music (D55)
                else:
                    pa, pb = s.a.mailbox("self_presence"), s.b.mailbox("self_presence")
                    want = {"left": 0, "right": 1}.get(self.music_mode, 1 if not pa.flags & IN_PLAY and pb.flags & IN_PLAY else 0)
                    self.solo = (self.music if self.music is not None else want) if same_sound(pa, pb) else None
                    if want != self.music:  # only that game plays music (the other's is muted in-game)
                        self.music = want
                        for i, g in enumerate(self.games):
                            g.mailbox("set_control", (0 if i == self.music else CONTROL_MUTE_MUSIC) | self.aggro)
                status, pres_list = self.status_line(clock)
                self.scene_speed = self.scene_speed_now()
                self.journal.note(self.frame, pres_list, getattr(self, "partner_state", None))
                status = self.stuck_note(pres_list) or status
                if self.moments:
                    for event, where in self.moments.check(pres_list):
                        self.moment(event, where)
                        self.say(f"Savestate: {event} {where}".strip(), 180)
            text = self.notice if self.frame < self.notice_until else status
            if self.rush and self.frame >= self.notice_until:
                text = f"{self.rush.text()}  ·  {status}"
            if self.goal and self.frame < 600:
                text = self.goal[:150]
            if not self.started:  # the game's boot: say so instead of the black (Tucker, 2026-10-26)
                self.started = self.frame > 3600 or any(f is not None and _not_black(f) for f in frames)
            if self.frame % 30 == 0:  # Settings > Show ping: the round trip to the partner, online
                self.display.corner = self.ping_text()
            if self.started:
                self.display.present_games(frames, [text], (255, 160, 160) if self.mismatch else (230, 230, 230))
            else:
                self.overlay("Starting the game", ["Reading your disc: about 10 seconds."])
            t2 = time.perf_counter()
            self.frame_times.append(round((time.perf_counter() - t0) * 1000, 2))
            if self.profile:
                prof.append((t1 - t0, t2 - t1, time.perf_counter() - t2))
                if len(prof) == 120:
                    print("ms per frame: games %.1f  draw %.1f  rest %.1f" % tuple(1000 * sum(x) / 120 for x in zip(*prof)), flush=True)
                    prof.clear()
            if time.time() - last_cards > 5:  # keep the memory cards on disk
                self.write_cards()
                last_cards = time.time()
            if self.frames and self.frame >= self.frames:
                break
            pacer.wait()
            clock.tick()  # for the status bar's fps
        self.write_cards()
        self.moment("Quit")
        if self.audio:
            self.audio.clear()
        return result
