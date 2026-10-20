"""Both games on screen: the frame loop the player app (app.py) and the dev presets (play.py)
share. Two games, two pads, one window, both games' sound with one game's music, joint saves,
savestates at moments worth going back to, and F9 bug reports."""

import collections
import threading
import time
from array import array

import pygame

from link.mailbox import (CONTROL_AGGRO_SHIFT, CONTROL_MUTE_MUSIC, CONTROL_NO_AGGRO, IN_PLAY,
                          ROLE_AUTHORITY, ROLE_GUEST)

SCALE = 2
W, H = 256, 240
BAR = 52
ROLLING_EVERY = 300   # frames between the in-memory states an F9 report keeps (never on disk)
REPORT_SECONDS = 60   # inputs and frame times an F9 report keeps

PAD_BUTTONS = {  # SDL game controller button -> PlayStation button name (harness/emu.py)
    pygame.CONTROLLER_BUTTON_A: "cross", pygame.CONTROLLER_BUTTON_B: "circle",
    pygame.CONTROLLER_BUTTON_X: "square", pygame.CONTROLLER_BUTTON_Y: "triangle",
    pygame.CONTROLLER_BUTTON_LEFTSHOULDER: "l1", pygame.CONTROLLER_BUTTON_RIGHTSHOULDER: "r1",
    pygame.CONTROLLER_BUTTON_BACK: "select", pygame.CONTROLLER_BUTTON_START: "start",
    pygame.CONTROLLER_BUTTON_DPAD_UP: "up", pygame.CONTROLLER_BUTTON_DPAD_DOWN: "down",
    pygame.CONTROLLER_BUTTON_DPAD_LEFT: "left", pygame.CONTROLLER_BUTTON_DPAD_RIGHT: "right",
}
KEYS = [  # per player: key -> button
    {pygame.K_UP: "up", pygame.K_DOWN: "down", pygame.K_LEFT: "left", pygame.K_RIGHT: "right",
     pygame.K_z: "cross", pygame.K_x: "square", pygame.K_c: "circle", pygame.K_v: "triangle",
     pygame.K_a: "l1", pygame.K_s: "r1", pygame.K_RETURN: "start", pygame.K_RSHIFT: "select"},
    {pygame.K_i: "up", pygame.K_k: "down", pygame.K_j: "left", pygame.K_l: "right",
     pygame.K_f: "cross", pygame.K_g: "square", pygame.K_h: "circle", pygame.K_t: "triangle",
     pygame.K_q: "l1", pygame.K_e: "r1", pygame.K_SPACE: "start", pygame.K_TAB: "select"},
]
FORMATS = {  # libretro pixel format -> (bits per pixel, RGB masks)
    0: (16, (0x7C00, 0x03E0, 0x001F, 0)),       # 0RGB1555
    1: (32, (0xFF0000, 0x00FF00, 0x0000FF, 0)),  # XRGB8888
    2: (16, (0xF800, 0x07E0, 0x001F, 0)),       # RGB565
}


def mix(sounds):
    """Both games' sound (16-bit stereo) mixed into one stream, clipped. Only one game plays
    music (CONTROL_MUTE_MUSIC), so the sum is mostly sound effects."""
    sounds = [x for x in sounds if x]
    if len(sounds) < 2:
        return sounds[0] if sounds else b""
    a, b = array("h", sounds[0][:len(sounds[0]) // 2 * 2]), array("h", sounds[1][:len(sounds[1]) // 2 * 2])
    if len(a) < len(b):
        a, b = b, a
    for i, v in enumerate(b):
        v += a[i]
        a[i] = 32767 if v > 32767 else -32768 if v < -32768 else v
    return a.tobytes()


class Audio:
    """The games' sound, through an SDL audio device fed from a small buffer."""

    def __init__(self):
        from pygame._sdl2 import audio as sdl_audio
        self.buf, self.lock = bytearray(), threading.Lock()
        self.dev = sdl_audio.AudioDevice(devicename=None, iscapture=False, frequency=44100,
                                         audioformat=sdl_audio.AUDIO_S16, numchannels=2, chunksize=1024,
                                         allowed_changes=0, callback=self._pull)
        self.dev.pause(0)

    def _pull(self, dev, mem):
        with self.lock:
            n = min(len(mem), len(self.buf))
            mem[:n] = self.buf[:n]
            del self.buf[:n]
        for i in range(n, len(mem)):
            mem[i] = 0

    def push(self, data):
        with self.lock:
            self.buf += data
            if len(self.buf) > 44100 * 4 // 5:  # over 0.2 s behind: drop the oldest
                del self.buf[:len(self.buf) - 44100 * 4 // 10]

    def clear(self):
        with self.lock:
            self.buf.clear()


def frame_surface(surf, fmt, pitch, height):
    """A surface the core's raw frame bytes can be written into as they are."""
    bits, masks = FORMATS[fmt]
    width = pitch * 8 // bits
    if surf is None or surf.get_size() != (width, height) or surf.get_bitsize() != bits:
        surf = pygame.Surface((width, height), 0, bits, masks)
    return surf


class Pads:
    """Controllers and the keyboard, as each player's pad. assign: the controllers' instance ids
    per player (the wizard sets them), or None for "the Nth controller"."""

    def __init__(self, assign=(None, None)):
        from pygame._sdl2 import controller as sdl_controller
        self.sdl = sdl_controller
        sdl_controller.init()
        self.assign = list(assign)
        self.refresh()

    def refresh(self):
        self.controllers = [self.sdl.Controller(i) for i in range(self.sdl.get_count()) if self.sdl.is_controller(i)]

    def names(self):
        return [c.name for c in self.controllers]

    def controller(self, player):
        want = self.assign[player] if player < len(self.assign) else None
        if want is not None:
            for c in self.controllers:
                if c.as_joystick().get_instance_id() == want:
                    return c
            return None
        return self.controllers[player] if player < len(self.controllers) else None

    def mask(self, player, keys):
        pressed = set()
        c = self.controller(player)
        if c is not None:
            pressed |= {name for btn, name in PAD_BUTTONS.items() if c.get_button(btn)}
            x, y = c.get_axis(pygame.CONTROLLER_AXIS_LEFTX), c.get_axis(pygame.CONTROLLER_AXIS_LEFTY)
            pressed |= {n for n, on in (("left", x < -16000), ("right", x > 16000), ("up", y < -16000),
                                        ("down", y > 16000)) if on}
            if c.get_axis(pygame.CONTROLLER_AXIS_TRIGGERLEFT) > 16000:
                pressed.add("l2")
            if c.get_axis(pygame.CONTROLLER_AXIS_TRIGGERRIGHT) > 16000:
                pressed.add("r2")
        pressed |= {name for key, name in KEYS[player].items() if keys[key]}
        return "+".join(sorted(pressed))


class GameView:
    """Runs both games in the window until the player leaves (ESC: the pause menu)."""

    def __init__(self, session, screen, pads, audio, playthrough=None, goal="", music="auto", aggro=50,
                 save_cards=None, frames=0, profile=False):
        self.s, self.screen, self.pads, self.audio = session, screen, pads, audio
        self.games = tuple(session.games)
        self.online = len(self.games) == 1
        self.playthrough, self.goal = playthrough, goal
        self.music_mode, self.music = music, None
        chance = max(0, min(255, round(aggro * 256 / 100)))
        self.aggro = CONTROL_NO_AGGRO if chance == 0 else chance << CONTROL_AGGRO_SHIFT
        self.save_cards = save_cards  # (path A, path B) or (path local,)
        self.frames, self.profile = frames, profile
        self.font = pygame.font.SysFont("consolas", 14)
        self.big = pygame.font.SysFont("georgia", 28)
        self.rolling = collections.deque(maxlen=2)
        self.inputs = collections.deque(maxlen=60 * REPORT_SECONDS)
        self.frame_times = collections.deque(maxlen=60 * REPORT_SECONDS)
        self.notice, self.notice_until = "", 0
        self.mismatch = None
        self.moments = None
        if playthrough:
            from archive import Moments
            self.moments = Moments(playthrough)

    def say(self, text, frames=300):
        self.notice, self.notice_until = text, self.frame + frames

    def moment(self, event, where=""):
        if self.playthrough:
            self.playthrough.savestate(event, self.games, where)
            self.playthrough.save_info()

    def ask_note(self):
        """"What happened?" Typed text, or "" (Enter on nothing, or Esc). The games wait."""
        snapshot = self.screen.copy()
        text = ""
        pygame.key.start_text_input()
        try:
            while True:
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT:
                        return text
                    if ev.type == pygame.TEXTINPUT and len(text) < 300:
                        text += ev.text
                    elif ev.type == pygame.KEYDOWN:
                        if ev.key == pygame.K_RETURN:
                            return text
                        if ev.key == pygame.K_ESCAPE:
                            return ""
                        if ev.key == pygame.K_BACKSPACE:
                            text = text[:-1]
                    elif ev.type == pygame.CONTROLLERBUTTONDOWN and ev.button in (pygame.CONTROLLER_BUTTON_A,
                                                                                    pygame.CONTROLLER_BUTTON_START):
                        return text
                self.screen.blit(snapshot, (0, 0))
                shade = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
                shade.fill((0, 0, 0, 190))
                self.screen.blit(shade, (0, 0))
                cx = self.screen.get_width() // 2
                for k, line in enumerate(("Report a problem: what happened? (optional)",
                                          "Type, then Enter to save the report (or press A / cross: no note). Esc: no note.")):
                    t = (self.big if k == 0 else self.font).render(line, True, (220, 200, 160))
                    self.screen.blit(t, (cx - t.get_width() // 2, 140 + k * 44))
                box = pygame.Rect(80, 230, self.screen.get_width() - 160, 40)
                pygame.draw.rect(self.screen, (30, 30, 40), box)
                pygame.draw.rect(self.screen, (220, 200, 160), box, 1)
                shown = text[-80:] + ("_" if pygame.time.get_ticks() // 400 % 2 else " ")
                self.screen.blit(self.font.render(shown, True, (240, 240, 240)), (box.x + 8, box.y + 12))
                pygame.display.flip()
                pygame.time.wait(16)
        finally:
            pygame.key.stop_text_input()
            self.screen.blit(snapshot, (0, 0))  # the report's window shot: the game, not this box

    def report(self, note=None):
        import report
        if note is None:
            note = self.ask_note()
        path = report.write(self.games, self.playthrough, self.screen, self.rolling, self.inputs,
                            self.frame_times, self.pads.names(), note)
        self.say(f"Bug report saved: {path.name} (in {path.parent})", 480)
        return path

    def write_cards(self):
        if self.save_cards:
            for g, path in zip(self.games, self.save_cards):
                path.write_bytes(g.card())

    def pause_menu(self):
        """ESC: Resume / Report a problem / Back to the menu. Returns "resume", "menu" or "quit"."""
        items = ["Resume", "Report a problem (F9)", "Save and go back to the menu"]
        sel = 0
        snapshot = self.screen.copy()
        if self.audio:
            self.audio.clear()
        while True:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    return "quit"
                move = None
                if ev.type == pygame.KEYDOWN:
                    move = {pygame.K_UP: -1, pygame.K_DOWN: 1}.get(ev.key)
                    if ev.key == pygame.K_ESCAPE:
                        return "resume"
                    if ev.key in (pygame.K_RETURN, pygame.K_z):
                        move = "ok"
                elif ev.type == pygame.CONTROLLERBUTTONDOWN:
                    move = {pygame.CONTROLLER_BUTTON_DPAD_UP: -1, pygame.CONTROLLER_BUTTON_DPAD_DOWN: 1,
                            pygame.CONTROLLER_BUTTON_A: "ok", pygame.CONTROLLER_BUTTON_B: "back"}.get(ev.button)
                if move == "back":
                    return "resume"
                if move == "ok":
                    if sel == 0:
                        return "resume"
                    if sel == 1:
                        self.screen.blit(snapshot, (0, 0))
                        self.report()
                        return "resume"
                    return "menu"
                if isinstance(move, int):
                    sel = (sel + move) % len(items)
            self.screen.blit(snapshot, (0, 0))
            shade = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
            shade.fill((0, 0, 0, 170))
            self.screen.blit(shade, (0, 0))
            cx = self.screen.get_width() // 2
            title = self.big.render("Paused", True, (220, 200, 160))
            self.screen.blit(title, (cx - title.get_width() // 2, 120))
            for k, text in enumerate(items):
                color = (255, 230, 150) if k == sel else (180, 180, 180)
                t = self.big.render(("> " if k == sel else "  ") + text, True, color)
                self.screen.blit(t, (cx - 220, 190 + k * 44))
            pygame.display.flip()
            pygame.time.wait(16)

    def run(self):
        """Returns when the player goes back to the menu (or closes the window): "menu" / "quit"."""
        s = self.s
        clock, self.frame, last_cards = pygame.time.Clock(), 0, time.time()
        lines, scaled, raw, prof = [], [None, None], [None, None], []
        result = "menu"
        while True:
            leave = None
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    leave = "quit"
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                    leave = self.pause_menu()
                    if leave == "resume":
                        leave = None
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F1:
                    self.music_mode = {"auto": "left", "left": "right", "right": "auto"}[self.music_mode]
                    self.music = None
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F9:
                    self.report()
                elif ev.type in (pygame.CONTROLLERDEVICEADDED, pygame.CONTROLLERDEVICEREMOVED):
                    self.pads.refresh()
            if leave:
                result = leave
                break
            keys = pygame.key.get_pressed()
            t0 = time.perf_counter()
            pads = [self.pads.mask(i, keys) for i in range(len(self.games))]
            self.inputs.append((self.frame, *pads))
            if self.frame % ROLLING_EVERY == 0:
                self.rolling.append((self.frame, *(g.save_state() for g in self.games)))
            for g, pad in zip(self.games, pads):  # both games run their frame at the same time
                g.frame_start(pad)
            replies = [g.frame_end() for g in self.games]
            t1 = time.perf_counter()
            if self.online:
                self.screen.fill((12, 8, 14), (0, 0, self.screen.get_width(), H * SCALE))
            for i, (g, (picture, sound)) in enumerate(zip(self.games, replies)):
                if picture:
                    w, h, fmt, pitch, n = picture
                    raw[i] = frame_surface(raw[i], fmt, pitch, h)
                    raw[i].get_buffer().write(bytes(g.shm.buf[:n]), 0)
                    if scaled[i] is None or scaled[i].get_bitsize() != raw[i].get_bitsize():
                        scaled[i] = pygame.Surface((W * SCALE, H * SCALE), 0, raw[i])
                    pygame.transform.scale(raw[i].subsurface((0, 0, w, h)), (W * SCALE, H * SCALE), scaled[i])
                    x = (self.screen.get_width() - W * SCALE) // 2 if self.online else i * (W * SCALE + 8)
                    self.screen.blit(scaled[i], (x, 0))
            if self.audio:
                self.audio.push(mix([sound for _, sound in replies]))
            self.frame += 1
            if s.joint and (self.online or self.frame % 15 == 0):  # online ticks every frame for save messages
                s.joint.tick()
            if self.frame % 15 == 0:
                if self.online:
                    g = self.games[0]
                    pa, pb = g.mailbox("self_presence"), g.mailbox("partner_presence")
                    age = g.mailbox("partner_age")
                    hst = g.host("status")
                    self.mismatch = hst.get("mismatch")
                    g.mailbox("set_control", self.aggro)  # online: never mute local music (D55)
                    pres_list = (pa, pb) if age <= 30 else (pa,)
                    if self.moments:
                        for event, where in self.moments.check(pres_list):
                            self.moment(event, where)
                            self.say(f"Savestate: {event} {where}".strip(), 180)
                    together = age <= 30 and {pa.role, pb.role} == {ROLE_AUTHORITY, ROLE_GUEST}
                    link_txt = self.mismatch or ("Partner connected" if age <= 180 else "Waiting for partner…")
                    status = (f"Online ({link_txt})   {'Together' if together else 'Apart'}   "
                              f"F9: report a problem   Esc: pause   {clock.get_fps():.0f} fps")
                else:
                    pa, pb = s.a.mailbox("self_presence"), s.b.mailbox("self_presence")
                    want = {"left": 0, "right": 1}.get(self.music_mode, 1 if not pa.flags & IN_PLAY and pb.flags & IN_PLAY else 0)
                    if want != self.music:  # only that game plays music (the other's is muted in-game)
                        self.music = want
                        for i, g in enumerate(self.games):
                            g.mailbox("set_control", (0 if i == self.music else CONTROL_MUTE_MUSIC) | self.aggro)
                    if self.moments:
                        for event, where in self.moments.check((pa, pb)):
                            self.moment(event, where)
                            self.say(f"Savestate: {event} {where}".strip(), 180)
                    together = {pa.role, pb.role} == {ROLE_AUTHORITY, ROLE_GUEST}
                    status = (f"{'Together' if together else 'Apart'}   music: {'left' if self.music == 0 else 'right'} "
                              f"({self.music_mode}, F1)   F9: report a problem   Esc: pause   {clock.get_fps():.0f} fps")
                text = [self.goal[:150]] if self.goal else []
                text.append(self.notice if self.frame < self.notice_until else status)
                lines = [self.font.render(t, True, (255, 160, 160) if self.mismatch else (230, 230, 230)) for t in text]
            self.screen.fill((16, 16, 24), (0, H * SCALE, self.screen.get_width(), BAR))
            for row, line in enumerate(lines):
                self.screen.blit(line, (6, H * SCALE + 4 + row * 18))
            t2 = time.perf_counter()
            pygame.display.flip()
            self.frame_times.append(round((time.perf_counter() - t0) * 1000, 2))
            if self.profile:
                prof.append((t1 - t0, t2 - t1, time.perf_counter() - t2))
                if len(prof) == 120:
                    print("ms per frame: games %.1f  draw %.1f  flip %.1f" % tuple(1000 * sum(x) / 120 for x in zip(*prof)), flush=True)
                    prof.clear()
            if time.time() - last_cards > 5:  # keep the memory cards on disk
                self.write_cards()
                last_cards = time.time()
            if self.frames and self.frame >= self.frames:
                break
            clock.tick(60)
        self.write_cards()
        self.moment("Quit")
        if self.audio:
            self.audio.clear()
        return result
