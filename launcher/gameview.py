"""Both games on screen: the frame loop the player app (app.py) and the dev presets (play.py)
share. Two games, two pads, one window (or two: launcher/display.py), both games' sound with one
game's music, joint saves, savestates at moments worth going back to, and F9 bug reports."""

import collections
import threading
import time
from array import array

import pygame

from link.mailbox import (CONTROL_AGGRO_SHIFT, CONTROL_MUTE_MUSIC, CONTROL_NO_AGGRO, IN_PLAY,
                          ROLE_AUTHORITY, ROLE_GUEST)
from winmenu import MENU_EVENT

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
    """Controllers and the keyboard, as each player's pad. assign: each player's controller
    (instance id), "kb" (keyboard only), or None ("the Nth controller")."""

    def __init__(self, assign=(None, None)):
        from pygame._sdl2 import controller as sdl_controller
        self.sdl = sdl_controller
        sdl_controller.init()
        self.assign = list(assign)
        self.virtual = {}  # tests (launcher/uxdriver.py): instance id -> {name, pressed buttons}
        self.refresh()

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
            pressed |= {name for btn, name in PAD_BUTTONS.items() if c.get_button(btn)}
            x, y = c.get_axis(pygame.CONTROLLER_AXIS_LEFTX), c.get_axis(pygame.CONTROLLER_AXIS_LEFTY)
            pressed |= {n for n, on in (("left", x < -16000), ("right", x > 16000), ("up", y < -16000),
                                        ("down", y > 16000)) if on}
            if c.get_axis(pygame.CONTROLLER_AXIS_TRIGGERLEFT) > 16000:
                pressed.add("l2")
            if c.get_axis(pygame.CONTROLLER_AXIS_TRIGGERRIGHT) > 16000:
                pressed.add("r2")
        want = self.assign[player] if player < len(self.assign) else None
        if want in self.virtual:
            pressed |= self.virtual[want]["pressed"]
        pressed |= {name for key, name in KEYS[player].items() if keys[key]}
        return "+".join(sorted(pressed))


class GameView:
    """Runs the games in the window until the player leaves (Esc: the pause menu)."""

    def __init__(self, session, display, pads, audio, playthrough=None, goal="", music="auto", aggro=50,
                 save_cards=None, frames=0, profile=False, launcher=None):
        self.s, self.display, self.pads, self.audio = session, display, pads, audio
        self.launcher = launcher
        self.games = tuple(session.games)
        self.online = len(self.games) == 1
        self.playthrough, self.goal = playthrough, goal
        self.music_mode, self.music = music, None
        chance = max(0, min(255, round(aggro * 256 / 100)))
        self.aggro = CONTROL_NO_AGGRO if chance == 0 else chance << CONTROL_AGGRO_SHIFT
        self.save_cards = save_cards  # (path A, path B) or (path local,)
        self.frames, self.profile = frames, profile
        self.canvas = display.canvas
        self.font = pygame.font.SysFont("consolas", 16)
        self.big = pygame.font.SysFont("georgia", 28)
        self.rolling = collections.deque(maxlen=2)
        self.inputs = collections.deque(maxlen=60 * REPORT_SECONDS)
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

    def say(self, text, frames=300):
        self.notice, self.notice_until = text, self.frame + frames

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

    def overlay(self, title, lines, items=(), sel=0, box_text=None):
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
        self.display.present(over_games=True)
        return rects

    def ask_note(self):
        """"What happened?" Typed text, or "" (Enter on nothing, or Esc). The games wait."""
        text = ""
        pygame.key.start_text_input()
        try:
            while True:
                for ev in pygame.event.get():
                    if self.display.handle(ev):
                        continue
                    if ev.type in (pygame.QUIT, pygame.WINDOWCLOSE):
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
                shown = text[-80:] + ("_" if pygame.time.get_ticks() // 400 % 2 else " ")
                self.overlay("Report a problem: what happened? (optional)",
                             ["Type, then Enter to save the report (or press Cross / A: no note). Esc: no note."],
                             box_text=shown)
                pygame.time.wait(16)
        finally:
            pygame.key.stop_text_input()

    def report(self, note=None):
        import report
        shot = self.display.screenshot()  # the window as it was: the games, not the note box
        if note is None:
            note = self.ask_note()
        path = report.write(self.games, self.playthrough, shot, self.rolling, self.inputs,
                            self.frame_times, self.pads.names(), note)
        self.say(f"Bug report saved: {path.name} (in {path.parent})", 480)
        return path

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
        from display import LAYOUT_NAMES, SCALING_NAMES
        sel = 0
        if self.audio:
            self.audio.clear()
        st = self.launcher.settings if self.launcher else self.display.settings
        while True:
            items = ["Resume",
                     f"Layout: {LAYOUT_NAMES.get(st.get('layout', 'auto'), 'Automatic')}",
                     f"Pixels: {SCALING_NAMES.get(st.get('scaling', 'sharp'), 'Sharp')}",
                     "How to play", "Report a problem (F9)", "Save and go back to the menu"]
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
                    if ev.key == pygame.K_ESCAPE:
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
                    if sel in (1, 2):  # cycle the layout / the pixels, as View in the menu bar
                        key, names = ("layout", LAYOUT_NAMES) if sel == 1 else ("scaling", SCALING_NAMES)
                        order = list(names)
                        now = st.get(key, order[0])
                        st[key] = order[(order.index(now) + 1) % len(order)] if now in order else order[0]
                        if self.launcher:
                            self.launcher.action(f"{key}:{st[key]}")
                        continue
                    if sel == 3:
                        if self.launcher:
                            self.launcher.action("help_play")
                        continue
                    if sel == 4:
                        self.report()
                        return "resume"
                    return "menu"
                if isinstance(move, int):
                    sel = (sel + move) % len(items)
            lines = [why] if why else []
            self._rects = self.overlay("Paused", lines, items, sel)
            pygame.time.wait(16)

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
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
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
        if self.online:
            g = self.games[0]
            hst = g.host("status")
            self.mismatch = hst.get("mismatch")
            age = g.mailbox("partner_age")
            pa, pb = g.mailbox("self_presence"), g.mailbox("partner_presence")
            together = age <= 30 and {pa.role, pb.role} == {ROLE_AUTHORITY, ROLE_GUEST}
            if self.mismatch:
                link = self.mismatch
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

    def run(self):
        """Returns when the player goes back to the menu (or closes the window): "menu", "quit"
        or ("navigate", action)."""
        s = self.s
        clock, self.frame, last_cards = pygame.time.Clock(), 0, time.time()
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
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
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
            frames = []
            for i, (g, (picture, sound)) in enumerate(zip(self.games, replies)):
                if picture:
                    w, h, fmt, pitch, n = picture
                    raw[i] = frame_surface(raw[i], fmt, pitch, h)
                    raw[i].get_buffer().write(bytes(g.shm.buf[:n]), 0)
                    frames.append(raw[i].subsurface((0, 0, w, h)))
                else:
                    frames.append(None)
            if self.audio:
                self.audio.push(mix([sound for _, sound in replies]))
            self.frame += 1
            if s.joint and (self.online or self.frame % 15 == 0):  # online ticks every frame for save messages
                s.joint.tick()
            if self.frame % 15 == 0:
                if self.online:
                    self.games[0].mailbox("set_control", self.aggro)  # online: never mute local music (D55)
                else:
                    pa, pb = s.a.mailbox("self_presence"), s.b.mailbox("self_presence")
                    want = {"left": 0, "right": 1}.get(self.music_mode, 1 if not pa.flags & IN_PLAY and pb.flags & IN_PLAY else 0)
                    if want != self.music:  # only that game plays music (the other's is muted in-game)
                        self.music = want
                        for i, g in enumerate(self.games):
                            g.mailbox("set_control", (0 if i == self.music else CONTROL_MUTE_MUSIC) | self.aggro)
                status, pres_list = self.status_line(clock)
                if self.moments:
                    for event, where in self.moments.check(pres_list):
                        self.moment(event, where)
                        self.say(f"Savestate: {event} {where}".strip(), 180)
            text = self.notice if self.frame < self.notice_until else status
            if self.goal and self.frame < 600:
                text = self.goal[:150]
            self.display.present_games(frames, [text], (255, 160, 160) if self.mismatch else (230, 230, 230))
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
            clock.tick(60)
        self.write_cards()
        self.moment("Quit")
        if self.audio:
            self.audio.clear()
        return result
