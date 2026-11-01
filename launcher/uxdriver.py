"""Plays the launcher like a person would, and photographs every screen (design/M7b-polish.md).

    python launcher/uxdriver.py couch     [--out DIR]   fresh install: disc, lobby, a new game,
                                                        a controller unplugged, pause, leave
    python launcher/uxdriver.py startup   [--out DIR]   Solo from a fresh install: seconds to the
                                                        first picture and to the title (M12 v1.0)
    python launcher/uxdriver.py window    [--out DIR]   every layout, resized,
                                                        maximized, fullscreen; frame times
    python launcher/uxdriver.py menus     [--out DIR]   every menu-bar item (Windows: through the
                                                        real menu bar's window procedure)
    python launcher/uxdriver.py test_castles [--out DIR]  COOP_DATA with test castles: Solo plays one from its start (D127)
    python launcher/uxdriver.py online    [--out DIR]   two launchers on this PC: one hosts, the
                                                        other types the room code; both play
    python launcher/uxdriver.py characters [--out DIR]  Settings › Game files: wrong discs refused in
                                                        plain words, then the DXC disc adds Maria;
                                                        Maria + Richter play (design/M8 criterion 5)

The real launcher runs, in a fresh data folder, with scripted input injected into its event
queue: keys, controller buttons (virtual controllers, launcher/gameview.Pads.virtual), menu-bar
clicks and typed text. A screenshot is saved each time a new screen appears. Screenshots of the
games are of game data: they go to --out (default .env/out/ux/<script>), never into git.
Exit code 0 = every step happened and every check held."""

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DEFAULT_OUT = ROOT / ".env" / "out" / "ux"


class Failed(Exception):
    pass


def window_image(hwnd, client=False):
    """One window as Windows draws it, frame and menu bar included (PrintWindow): never brought
    to the front, and nothing else on the screen is captured. client: only its client area (what
    the player sees of the games, under the menu bar)."""
    import ctypes
    from ctypes import wintypes
    from PIL import Image
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    r = wintypes.RECT()
    if client:
        u.GetClientRect(hwnd, ctypes.byref(r))
    else:
        u.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    hdc = u.GetWindowDC(hwnd)
    mem = g.CreateCompatibleDC(hdc)
    bmp = g.CreateCompatibleBitmap(hdc, w, h)
    g.SelectObject(mem, bmp)
    u.PrintWindow(hwnd, mem, 3 if client else 2)  # PW_RENDERFULLCONTENT (| PW_CLIENTONLY)

    class BMI(ctypes.Structure):
        _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                    ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                    ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long),
                    ("biYPelsPerMeter", ctypes.c_long), ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]
    bmi = BMI(ctypes.sizeof(BMI), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    g.GetDIBits(mem, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    g.DeleteObject(bmp)
    g.DeleteDC(mem)
    u.ReleaseDC(hwnd, hdc)
    return Image.frombuffer("RGB", (w, h), buf.raw, "raw", "BGRX", 0, 1)


class Driver:
    """Hooks pygame.event.get: each call, the next step runs once its condition holds."""

    def __init__(self, steps, out, launcher_cls):
        import pygame
        self.pg = pygame
        self.steps = list(steps)
        self.out = out
        self.heading = None
        self.subtitle = ""
        self.first_seen = {}  # screen -> when it first appeared (perf_counter): the startup script
        self.marks = {}
        self.view = None  # the GameView while the games run
        self.log = []
        self.checks = []
        self.shots = []
        self.inputs = 0
        self.waited = 0
        self.t0 = time.time()
        self.launcher = None
        self._real_get = pygame.event.get
        pygame.event.get = self.get
        drv = self
        orig_init = launcher_cls.__init__

        def init(this, *a, **kw):
            orig_init(this, *a, **kw)
            drv.launcher = this
            drv._hook_display(this.display)
            drv._hook_ui(this.ui)
        launcher_cls.__init__ = init
        import gameview
        orig_overlay = gameview.GameView.overlay

        def overlay(this, title, *a, **kw):
            drv.screen(title)
            return orig_overlay(this, title, *a, **kw)
        gameview.GameView.overlay = overlay
        orig_view_init = gameview.GameView.__init__

        def view_init(this, *a, **kw):
            orig_view_init(this, *a, **kw)
            drv.view = this
        gameview.GameView.__init__ = view_init
        self.game_frames = 0
        self.intervals = []
        self._last_present = None
        self.fps = {}  # screenshot -> frames per second just before it
        self.perf = {}  # perf script: size -> steady frames per second

    def _hook_ui(self, ui):
        orig = ui.frame
        drv = self

        def frame(heading, subtitle=""):
            drv.screen(heading or "Home")
            drv.subtitle = subtitle
            return orig(heading, subtitle)
        ui.frame = frame

    def _hook_display(self, display):
        orig_present, orig_games = display.present, display.present_games
        drv = self

        def present(over_games=False):
            orig_present(over_games)
            drv._maybe_shot()

        def present_games(frames, *a, **kw):
            drv.game_frames += 1
            now = time.perf_counter()
            if drv._last_present is not None:
                drv.intervals.append(now - drv._last_present)
            drv._last_present = now
            drv.screen("Game")
            orig_games(frames, *a, **kw)
            drv._maybe_shot()
        display.present, display.present_games = present, present_games

    def screen(self, heading):
        if heading != self.heading:
            self.heading = heading
            self._new = True
            self.first_seen.setdefault(heading, time.perf_counter())

    def _maybe_shot(self, name=None):
        if getattr(self, "_new", False) or name:
            self._new = False
            slug = re.sub(r"[^a-z0-9]+", "-", (name or self.heading or "screen").lower()).strip("-")[:40]
            path = self.out / f"{len(self.shots) + 1:02d}-{slug}.png"
            try:
                self.pg.image.save(self.launcher.display.screenshot(), str(path))
                self.shots.append(path.name)
                recent = self.intervals[-60:]
                if self.heading == "Game" and len(recent) >= 20:
                    self.fps[path.name] = round(len(recent) / sum(recent), 1)
                    self.intervals.clear()
            except Exception as e:  # noqa: BLE001
                self.log.append(f"screenshot failed: {e}")

    def check(self, ok, what, **info):
        self.checks.append({"ok": bool(ok), "what": what, **info})
        print(("ok   " if ok else "FAIL ") + what, info if info else "", flush=True)
        if not ok:
            raise Failed(what)

    # --- the steps

    def post_key(self, key, mod=0):
        pg = self.pg
        pg.event.post(pg.event.Event(pg.KEYDOWN, key=key, mod=mod, unicode="", scancode=0))
        pg.event.post(pg.event.Event(pg.KEYUP, key=key, mod=mod, unicode="", scancode=0))

    def post_pad(self, iid, button):
        pg = self.pg
        pads = self.launcher.pads
        pads.virtual.setdefault(iid, {"name": f"Test controller {iid}", "pressed": set()})
        pg.event.post(pg.event.Event(pg.CONTROLLERBUTTONDOWN, instance_id=iid, button=button))
        pg.event.post(pg.event.Event(pg.CONTROLLERBUTTONUP, instance_id=iid, button=button))

    def get(self, *a, **kw):
        try:
            self.tick()
        except Failed:
            raise
        except Exception as e:  # noqa: BLE001
            self.checks.append({"ok": False, "what": f"step crashed: {e!r}"})
            raise
        return self._real_get(*a, **kw)

    def tick(self):
        if not self.steps or self.launcher is None:
            return
        step = self.steps[0]
        kind, args = step[0], step[1:]
        pg = self.pg
        self.waited += 1
        if self.waited > 6000:
            self.check(False, f"timed out waiting for {step!r}", heading=self.heading)
        if kind == "screen":
            if not (self.heading and args[0].lower() in self.heading.lower()):
                return
        elif kind == "game_frames":
            if self.game_frames < args[0]:
                return
        elif kind == "wait":
            if self.waited < args[0]:
                return
        elif kind == "until":
            if not args[0](self):
                return
        elif kind == "key":
            self.post_key(args[0], args[1] if len(args) > 1 else 0)
            self.inputs += 1
        elif kind == "pad":
            self.post_pad(*args)
            self.inputs += 1
        elif kind == "hold":
            iid, buttons = args
            self.launcher.pads.virtual[iid]["pressed"] = set(buttons.split("+")) if buttons else set()
        elif kind == "unplug":
            self.launcher.pads.virtual.pop(args[0], None)
            pg.event.post(pg.event.Event(pg.CONTROLLERDEVICEREMOVED, instance_id=args[0]))
        elif kind == "menu":
            mb = self.launcher.menubar
            if mb.ok:
                mb.click(args[0])  # through the real window procedure
            else:
                from winmenu import MENU_EVENT
                pg.event.post(pg.event.Event(MENU_EVENT, action=args[0]))
            self.inputs += 1
        elif kind == "type":
            for ch in args[0]:
                pg.event.post(pg.event.Event(pg.TEXTINPUT, text=ch))
            self.inputs += 1
        elif kind == "type_file":
            p = Path(args[0])
            if not p.exists():
                return
            for ch in p.read_text().strip():
                pg.event.post(pg.event.Event(pg.TEXTINPUT, text=ch))
            self.inputs += 1
        elif kind == "call":
            args[0](self)
        elif kind == "shot":
            self._maybe_shot(args[0])
            audio = getattr(self.launcher, "audio", None)
            if audio is not None and hasattr(audio, "stats"):
                print(f"audio at {args[0]}: {audio.stats()}", flush=True)
        elif kind == "winshot":  # Windows: the whole window, title and menu bar too
            if sys.platform == "win32":
                mb = self.launcher.menubar
                img = window_image(mb.hwnd) if mb.ok else None
                if img:
                    img.save(self.out / f"win-{args[0]}.png")
                    self.shots.append(f"win-{args[0]}.png")
                self.check(mb.ok, "the native menu bar is installed")
        elif kind == "expect":
            self.check(args[0](self), args[1])
        elif kind == "count_inputs":
            self.inputs = 0
        self.log.append({"t": round(time.time() - self.t0, 2), "step": repr(step)[:120], "screen": self.heading})
        self.steps.pop(0)
        self.waited = 0

    def report(self, error=None):
        rep = {"passed": error is None and not self.steps and all(c["ok"] for c in self.checks),
               "error": error, "left": [repr(s)[:100] for s in self.steps], "checks": self.checks,
               "inputs": self.inputs, "shots": self.shots, "fps": self.fps, "perf": self.perf, "log": self.log,
               "seconds": round(time.time() - self.t0, 1)}
        (self.out / "report.json").write_text(json.dumps(rep, indent=1, default=str))
        return rep


def run(script, out, retail_cue=None):
    """Runs one scripted session of the real launcher in this process."""
    out.mkdir(parents=True, exist_ok=True)
    import logging  # the connector's steps (link/connect.py), into the test's output and logcat
    logging.basicConfig(level=logging.INFO, stream=sys.stderr, format="%(name)s %(message)s")
    for f in out.glob("*.png"):
        f.unlink()
    if "COOP_DATA" not in os.environ:
        os.environ["COOP_DATA"] = tempfile.mkdtemp(prefix="coop-ux-")
    if retail_cue:
        os.environ["COOP_PICK_FILE"] = str(retail_cue)
    if not (ROOT / "bios" / "openbios-fast.bin").exists():  # a dev checkout: the OpenBIOS the release ships
        sys.path.insert(0, str(ROOT / "harness"))
        from coop_env import TOOLS
        openbios = TOOLS["bios_dir"] / "scph5501.bin"   # OpenBIOS, FASTBOOT (scripts/bootstrap.sh)
        if openbios.exists():
            os.environ.setdefault("COOP_DEV_BIOS", str(openbios))
    dev_patch = ROOT / ".env" / "release" / "sotn-coop.bps"
    if not (ROOT / "patcher" / "sotn-coop.bps").exists() and dev_patch.exists():
        os.environ.setdefault("COOP_PATCH", str(dev_patch))
    sys.path.insert(0, str(HERE))
    if os.environ.get("COOP_UX_BEHIND") and sys.platform == "win32":
        # Windows, while someone uses the PC: our windows are made hidden, put behind every other
        # window, then shown without being activated. Never in the way, and PrintWindow can
        # still read them (an off-screen window isn't drawn at all).
        import ctypes
        import pygame._sdl2.video as video
        real = video.Window

        def behind(title, *a, **kw):
            kw["hidden"] = True
            win = real(title, *a, **kw)
            u = ctypes.windll.user32
            hwnd = u.FindWindowW(None, title)
            u.SetWindowPos(hwnd, 1, 0, 0, 0, 0, 0x13)  # HWND_BOTTOM; no move, size or activation
            u.ShowWindow(hwnd, 8)  # SW_SHOWNA
            return win
        video.Window = behind
        import display
        display.Window = behind
    import app
    import pygame
    steps = SCRIPTS[script](pygame)
    drv = Driver(steps, out, app.Launcher)
    error = None
    try:
        launcher = app.Launcher()
        if os.environ.get("COOP_UX_NO_AUDIO"):
            if launcher.audio is not None:
                launcher.audio.close()  # no device left open either (its thread)
            launcher.audio = None
        try:
            launcher.wizard()
            launcher.home()
        except SystemExit:
            pass
        finally:
            launcher.display.remember()
    except Failed as e:
        error = str(e)
    except Exception as e:  # noqa: BLE001
        import traceback
        error = traceback.format_exc()
        print(error)
    finally:
        pygame.event.get = drv._real_get
    rep = drv.report(error)
    if rep["perf"]:
        print("  frames per second:", rep["perf"])
    print(f"{'PASSED' if rep['passed'] else 'FAILED'} {script}: {len(rep['shots'])} screens, "
          f"{rep['inputs']} inputs after the disc, {rep['seconds']} s  ->  {out}")
    if rep["left"]:
        print("  steps left:", rep["left"][:3])
    return rep


# --- the scripts

def _couch(pg, quit_at_end=True):
    A = pg.CONTROLLER_BUTTON_A
    B = pg.CONTROLLER_BUTTON_B
    L = pg.CONTROLLER_BUTTON_DPAD_LEFT
    in_game = lambda d: d.heading == "Game"
    return [
        ("screen", "Welcome"), ("shot", "welcome"),
        ("key", pg.K_RETURN),                                # Choose my disc image (picker: COOP_PICK_FILE)
        ("screen", "Co-op disc ready"), ("key", pg.K_RETURN),
        ("count_inputs",),
        ("screen", "Home"), ("key", pg.K_DOWN), ("key", pg.K_RETURN),  # Couch co-op (Solo is first)
        ("screen", "Press a button"), ("shot", "lobby-empty"),
        ("pad", 0, A),                                      # player 1 joins (id 0, like the first real controller)
        ("pad", 101, A),                                      # player 2 joins
        ("wait", 3), ("shot", "lobby-joined"),
        ("pad", 101, B),                                      # player 2 leaves...
        ("wait", 3), ("shot", "lobby-p2-left"),
        ("pad", 101, pg.CONTROLLER_BUTTON_X),                 # ...and comes back (any button)
        ("pad", 0, A), ("wait", 2), ("shot", "lobby-p1-ready"),
        ("pad", 101, L), ("wait", 3), ("shot", "lobby-maria-locked"),  # Maria: no DXC disc yet
        ("pad", 101, A),                                      # can't be ready as Maria: it opens Game files
        ("screen", "Game files"), ("shot", "game-files-from-lobby"),
        ("key", pg.K_ESCAPE), ("screen", "Press a button"),
        ("expect", lambda d: d.launcher.shortcuts(1), "shortcuts start on"),
        ("pad", 101, pg.CONTROLLER_BUTTON_Y), ("wait", 3), ("shot", "lobby-shortcuts-off"),
        ("expect", lambda d: not d.launcher.shortcuts(1) and d.launcher.shortcuts(0), "Triangle / Y: player 2's shortcuts off, player 1's on"),
        ("pad", 101, L), ("wait", 3), ("shot", "lobby-richter"),  # Richter
        ("pad", 101, A),                                      # both ready: New game (no playthroughs yet)
        ("screen", "Name your castle"), ("pad", 0, A),        # A, empty: named at the game's name entry
        ("until", in_game), ("expect", lambda d: d.inputs <= 15, "home to playing in 15 inputs or fewer (12, plus the detours to Game files and shortcuts)"),
        ("expect", lambda d: d.launcher.characters == [0, 1] and d.launcher.options(0) & 1 and not d.launcher.options(1) & 1,
         "player 1 plays Alucard with shortcuts, player 2 Richter without"),
        ("game_frames", 900), ("shot", "both-games"), ("game_frames", 2000), ("shot", "both-games-later"),
        ("hold", 0, "start"), ("game_frames", 2060), ("hold", 0, ""), ("game_frames", 2200),
        ("unplug", 101),
        ("screen", "controller disconnected"), ("shot", "unplugged"),
        ("pad", 102, A),                                      # any controller: it's player 2's now
        ("until", in_game), ("expect", lambda d: d.launcher.pads.assign[1] == 102, "a new controller takes over player 2"),
        ("game_frames", 2300),
        ("key", pg.K_ESCAPE), ("screen", "Paused"), ("shot", "paused"),
        ("key", pg.K_DOWN), ("key", pg.K_RETURN), ("wait", 3),  # Layout: Automatic -> Side by side
        ("expect", lambda d: d.launcher.settings.get("layout") == "side", "the pause menu changes the layout (View, from a controller)"),
        ("call", lambda d: d.launcher.action("layout:auto")),
        ("key", pg.K_UP), ("key", pg.K_UP), ("key", pg.K_RETURN),  # Save and go back to the menu
        ("screen", "Home"), ("shot", "home-again"),
    ] + ([("key", pg.K_UP), ("key", pg.K_RETURN)] if quit_at_end else [])  # Quit


def _solo(pg):
    """M11 criterion 1, from the launcher: Home > Solo plays a new castle at once (no castles
    yet); back on Home, Solo lists it."""
    A = pg.CONTROLLER_BUTTON_A
    in_game = lambda d: d.heading == "Game"

    def castles():
        from archive import Castle
        return Castle.all()
    return [
        ("screen", "Welcome"), ("key", pg.K_RETURN),
        ("screen", "Co-op disc ready"), ("key", pg.K_RETURN),
        ("count_inputs",),
        ("screen", "Home"), ("shot", "home"), ("key", pg.K_RETURN),  # Solo: the first item
        ("screen", "Name your castle"), ("pad", 0, A),
        ("screen", "Press a button"), ("pad", 0, A), ("pad", 0, A),
        ("until", in_game), ("expect", lambda d: d.inputs <= 4, "home to playing solo in 4 inputs"),
        ("expect", lambda d: len(castles()) == 1, "a new castle"),
        ("game_frames", 900), ("shot", "solo-game"),
        ("expect", lambda d: d.launcher.display._bar_key[0][0].startswith("Solo"), "the status bar says Solo, no partner"),
        ("game_frames", 3000), ("shot", "solo-game-later"),
        ("key", pg.K_ESCAPE), ("screen", "Paused"), ("key", pg.K_UP), ("key", pg.K_RETURN),
        ("screen", "Home"), ("key", pg.K_RETURN),
        ("screen", "Solo: which castle?"), ("shot", "castle-list"),
        ("expect", lambda d: len(castles()) == 1 and castles()[0].info.get("played"), "it lists the castle played (the list is New castle and it)"),
        ("key", pg.K_ESCAPE), ("screen", "Home"), ("key", pg.K_UP), ("key", pg.K_RETURN),  # Quit
    ]


def _test_castles(pg):
    """Test castles (D127), with COOP_DATA holding a castle and the test castles: Solo > Test castles >
    the first (Slogra & Gaibon) plays a fresh copy, and the game arrives at its start."""
    A = pg.CONTROLLER_BUTTON_A

    def at_start(d):
        from archive import Castle
        played = [c for c in Castle.all() if c.info.get("start")]
        g = d.view.games[0] if d.view and d.view.games else None
        if not played or g is None:
            return False
        p, want = g.mailbox("self_presence"), played[0].info["start"]
        return [p.stage, p.room_id] == want[:2] and abs(p.x - want[2]) < 16  # the save alone: x 128
    return [
        ("screen", "Welcome"), ("key", pg.K_RETURN), ("screen", "Co-op disc ready"), ("key", pg.K_RETURN),
        ("screen", "Home"), ("key", pg.K_RETURN),
        ("screen", "Solo: which castle?"), ("key", pg.K_UP), ("shot", "castle-list"), ("key", pg.K_RETURN),  # the last item
        ("screen", "Test castles"), ("shot", "test-castles"), ("key", pg.K_RETURN),
        ("screen", "Press a button"), ("pad", 0, A), ("pad", 0, A),
        ("until", lambda d: d.heading == "Game"),
        ("until", lambda d: at_start(d) or d.waited > 20000),
        ("call", lambda d: setattr(d, "arrived", d.view.frame)),  # then past the room's fade in
        ("until", lambda d: d.view.frame > d.arrived + 150 or d.waited > 20000), ("shot", "at-the-boss"),
        ("expect", at_start, "the fresh copy plays from its start, outside Slogra & Gaibon"),
        ("key", pg.K_ESCAPE), ("screen", "Paused"), ("key", pg.K_UP), ("key", pg.K_RETURN),
        ("screen", "Home"), ("key", pg.K_UP), ("key", pg.K_RETURN),  # Quit
    ]


def _startup(pg):
    """design/M12-v1-release.md criterion 6 (the launch black screen, D114): from pressing Solo,
    a picture (the "Starting the game" overlay or the game) within 1 s, and the title screen within
    20 s. Times are wall-clock, at the launcher's real 60 fps."""
    A = pg.CONTROLLER_BUTTON_A

    def mark(d, name):
        d.marks.setdefault(name, time.perf_counter())

    def state(d):
        return d.view.games[0].read("g_GameState") if d.view and d.view.games else None  # between frames (events)

    def title(d):
        if state(d) in (1, 2):  # GAME_TITLE_STATE, GAME_PLAY_STATE (harness/emu.py)
            mark(d, "title")
        return "title" in d.marks

    def report(d):
        t0 = d.marks["pressed"]
        first = min(t for k, t in d.first_seen.items() if k in ("Starting the game", "Game") and t >= t0)
        d.startup = {"picture_s": round(first - t0, 2), "game_picture_s": round(d.first_seen["Game"] - t0, 2),
                     "title_s": round(d.marks["title"] - t0, 2), "title_frame": d.view.frame}
        print("startup:", d.startup, flush=True)
    return [
        ("screen", "Welcome"), ("key", pg.K_RETURN),
        ("screen", "Co-op disc ready"), ("key", pg.K_RETURN),
        ("screen", "Home"), ("key", pg.K_RETURN),
        ("screen", "Name your castle"), ("pad", 0, A),
        ("screen", "Press a button"), ("pad", 0, A), ("call", lambda d: mark(d, "pressed")), ("pad", 0, A),
        ("until", lambda d: "Game" in d.first_seen), ("shot", "first-picture"),
        ("until", title), ("shot", "title"), ("call", report),
        ("expect", lambda d: d.startup["picture_s"] <= 1.0, "a picture within 1 s of pressing Solo"),
        ("expect", lambda d: d.startup["title_s"] <= 20.0, "the title within 20 s"),
        ("key", pg.K_ESCAPE), ("screen", "Paused"), ("key", pg.K_UP), ("key", pg.K_RETURN),
        ("screen", "Home"), ("key", pg.K_UP), ("key", pg.K_RETURN),  # Quit
    ]


def _window(pg):
    steps = _couch(pg, quit_at_end=False)[:-2]
    i = next(k for k, s in enumerate(steps) if s[0] == "unplug")
    steps = steps[:i]  # into the game, both playing

    for layout in ("side", "stacked", "p1", "p2", "windows", "auto"):
        steps += [("menu", f"layout:{layout}"), ("wait", 20), ("shot", layout)]
    for w, h in ((1280, 720), (1920, 1080), (1080, 1920), (700, 400)):
        steps += [("call", lambda d, w=w, h=h: setattr(d.launcher.display.window, "size", (w, h))),
                  ("wait", 20), ("shot", f"resized-{w}x{h}")]
    steps += [("menu", "fullscreen"), ("wait", 30), ("shot", "fullscreen"), ("menu", "fullscreen"),
              ("call", lambda d: d.launcher.display.window.maximize()), ("wait", 30), ("shot", "maximized"),
              ("key", pg.K_ESCAPE), ("screen", "Paused"), ("key", pg.K_UP), ("key", pg.K_RETURN),
              ("screen", "Home"),
              ("expect", lambda d: d.launcher.settings.get("layout") == "auto", "the layout is remembered"),
              ("key", pg.K_UP), ("key", pg.K_RETURN)]
    return steps


def _menus(pg):
    steps = [("screen", "Welcome"), ("key", pg.K_RETURN), ("screen", "Co-op disc ready"), ("key", pg.K_RETURN),
             ("screen", "Home"), ("wait", 30), ("winshot", "home")]
    for action, screen in (("help_play", "How to play"), ("help_online", "Online troubleshooting"),
                           ("keys", "Keyboard keys"), ("about", "About")):
        steps += [("menu", action), ("screen", screen), ("shot", action), ("key", pg.K_RETURN), ("screen", "Home")]
    for action in ("layout:stacked", "netsim:wifi", "netsim:off", "layout:auto"):
        steps += [("menu", action), ("wait", 5)]
    steps += [("expect", lambda d: d.launcher.settings.get("layout") == "auto" and not d.launcher.settings.get("netsim"),
               "View and Developer menu items change the settings")]
    for action, screen in (("savestates", "Savestates"), ("debug_starts", "Debug starts"), ("controllers", "Press a button"),
                           ("new", "Press a button"), ("continue", "Press a button")):
        steps += [("menu", action), ("screen", screen), ("shot", action), ("key", pg.K_ESCAPE),
                  ("screen", "Home")] if screen != "Debug starts" else [
                  ("menu", action), ("until", lambda d: d.heading in ("Debug starts", "Making the debug starts")),
                  ("until", lambda d: d.heading == "Debug starts"), ("shot", action), ("key", pg.K_ESCAPE),
                  ("screen", "Home")]
    steps += [("menu", "quit")]
    return steps


def _to_online(pg):
    """Home to Online co-op: after Solo and Couch, or after Solo on Android (no couch there: design/M9)."""
    from platform_android import ANDROID
    return [("key", pg.K_DOWN)] * (1 if ANDROID else 2)


def _picture_lit(d):
    """The game's picture isn't black (its last frame: some pixels lit)."""
    import pygame
    games = d.launcher.display.games
    f = games[0]._last if games else None
    if f is None:
        return False
    small = pygame.transform.scale(f, (64, 48))
    return sum(1 for x in range(64) for y in range(48) if sum(small.get_at((x, y))[:3]) > 60) > 100


def _android_picture(name):
    """On Android, play on to the title and check the game draws (design/M9)."""
    from platform_android import ANDROID
    if not ANDROID:
        return []
    return [("game_frames", 2400), ("shot", name + "-later"),
            ("expect", _picture_lit, "the game draws (the picture isn't black)")]


def _online_host(pg, code_file):
    A = pg.CONTROLLER_BUTTON_A

    def write_code(d):
        room = d.launcher.room_info.split("room ")[1].split(",")[0]
        Path(code_file).write_text(room)
    return [("screen", "Welcome"), ("key", pg.K_RETURN), ("screen", "Co-op disc ready"), ("key", pg.K_RETURN),
            ("count_inputs",),
            ("screen", "Home"), *_to_online(pg), ("key", pg.K_RETURN),
            ("screen", "Online co-op"), ("key", pg.K_RETURN),                 # Host: new game
            ("screen", "Name your castle"), ("type", "Tucker"), ("key", pg.K_RETURN),
            ("screen", "Press a button"), ("call", write_code), ("shot", "host-waiting"),
            ("pad", 100, A), ("pad", 100, A),
            ("until", lambda d: d.heading == "Game"), ("game_frames", 900), ("shot", "host-playing"),
            ("expect", lambda d: "Partner connected" in d.launcher.display._bar_key[0][0], "the host sees its partner connected"),
            *_android_picture("host-playing"),
            # The host stays until its partner leaves (a slower partner, a phone, checks later).
            ("until", lambda d: "Partner connected" not in d.launcher.display._bar_key[0][0] or d.waited > 5000),
            # the game pauses itself to say the partner left (gameview.partner_gone): no Esc
            ("screen", "Paused"), ("key", pg.K_UP), ("key", pg.K_RETURN),
            ("screen", "Online co-op"), ("key", pg.K_ESCAPE), ("screen", "Home"), ("menu", "quit")]


def _online_join(pg, code_file):
    A = pg.CONTROLLER_BUTTON_A
    return [("screen", "Welcome"), ("key", pg.K_RETURN), ("screen", "Co-op disc ready"), ("key", pg.K_RETURN),
            ("count_inputs",),
            ("screen", "Home"), *_to_online(pg), ("key", pg.K_RETURN),
            ("screen", "Online co-op"), ("key", pg.K_DOWN), ("key", pg.K_RETURN),  # Join your partner
            ("screen", "Join your partner"),
            *[("key", pg.K_BACKSPACE)] * 24,  # the box starts with a code on the clipboard (the host's)
            ("type_file", code_file), ("key", pg.K_RETURN),
            ("screen", "Press a button"), ("shot", "join-lobby"),
            # Tucker's presses on his PC (2026-10-22): A joins, Start readies, on the first real
            # controller (id 0)
            ("pad", 0, A), ("pad", 0, pg.CONTROLLER_BUTTON_START),
            ("until", lambda d: d.heading == "Game"), ("game_frames", 900), ("shot", "join-playing"),
            ("expect", lambda d: "Partner connected" in d.launcher.display._bar_key[0][0], "the joiner sees its partner connected"),
            ("expect", lambda d: (_received_castle() or "").startswith("Tucker_"),
             "the joiner keeps a copy of the host's castle, with the name the host gave it (design/M11)"),
            *_android_picture("join-playing"),
            ("key", pg.K_ESCAPE), ("screen", "Paused"), ("key", pg.K_UP), ("key", pg.K_RETURN),
            ("screen", "Online co-op"), ("key", pg.K_ESCAPE), ("screen", "Home"), ("menu", "quit")]


def _received_castle():
    """The joiner's copy of the host's castle (Castle.receive, at connect): its name and id."""
    from archive import Castle
    got = [c for c in Castle.all() if c.info.get("received") and c.info.get("id")]
    return got and got[0].name


def _perf(pg):
    """Steady frame rate at the sizes people play at: 5 s each, after 1 s to settle."""
    steps = _couch(pg, quit_at_end=False)
    steps = steps[:next(k for k, s in enumerate(steps) if s[0] == "unplug")]

    def size(w, h):
        return ("call", lambda d: setattr(d.launcher.display.window, "size", (w, h)))

    def measure(name):
        return [("wait", 60), ("call", lambda d: d.intervals.clear()), ("wait", 300),
                ("call", lambda d, name=name: d.perf.__setitem__(name, round(len(d.intervals) / max(1e-6, sum(d.intervals)), 1)))]
    for layout in ("auto", "windows"):
        steps += [("menu", f"layout:{layout}")]
        for name, how in (("1032x592", size(1032, 592)), ("1920x1080", size(1920, 1080)),
                          ("maximized", ("call", lambda d: d.launcher.display.window.maximize())),
                          ("fullscreen", ("menu", "fullscreen"))):
            steps += [how] + measure(f"{layout} {name}")
            if name == "fullscreen":
                steps += [("menu", "fullscreen"), ("call", lambda d: d.launcher.display.window.restore())]
    steps += [("menu", "layout:auto"),
              ("expect", lambda d: min(d.perf.values()) >= 55, "60 fps (55+) at every size and layout"),
              ("key", pg.K_ESCAPE), ("screen", "Paused"), ("key", pg.K_UP), ("key", pg.K_RETURN),
              ("screen", "Home"), ("key", pg.K_UP), ("key", pg.K_RETURN)]
    return steps


def _characters(pg):
    """Settings › Game files: three wrong files refused in plain words, then the DXC disc adds Maria
    (design/M8 criterion 5). Then Maria (player 1) and Richter (player 2) start a game."""
    import test_characters
    A, L, R = pg.CONTROLLER_BUTTON_A, pg.CONTROLLER_BUTTON_DPAD_LEFT, pg.CONTROLLER_BUTTON_DPAD_RIGHT
    tmp = Path(tempfile.mkdtemp(prefix="coop-ux-files-"))
    junk = tmp / "notes.txt"
    junk.write_bytes(b"hello" * 2000)
    wrong = [(test_characters.fake_psp_iso(tmp / "Castlevania DXC (Europe).iso", "ULES-00841"), "ULUS-10277", "eu"),
             (next((ROOT / "disks").glob("*Track 1).bin")), "PlayStation disc", "ps1"),
             (junk, "isn't a disc image", "junk")]

    def pick(path):
        return ("call", lambda d: os.environ.__setitem__("COOP_PICK_FILE", str(path)))
    steps = [("screen", "Welcome"), ("key", pg.K_RETURN), ("screen", "Co-op disc ready"), ("key", pg.K_RETURN),
             ("screen", "Home"), *[("key", pg.K_DOWN)] * 3, ("key", pg.K_RETURN),
             ("screen", "Settings"), *[("key", pg.K_DOWN)] * 5, ("key", pg.K_RETURN),
             ("screen", "Game files"), ("shot", "game-files-first"),
             ("expect", lambda d: not d.launcher.maria_ready(), "no Maria before her disc")]
    for path, words, name in wrong:
        steps += [pick(path), ("key", pg.K_DOWN), ("key", pg.K_RETURN),
                  ("screen", "That disc won't work"), ("shot", f"dxc-wrong-{name}"),
                  ("expect", lambda d, w=words: w in d.subtitle, f"{name}: the error says {words!r}"),
                  ("key", pg.K_RETURN), ("screen", "Game files")]
    steps += [pick(ROOT / "disks" / "sotn.pspus.iso"), ("key", pg.K_DOWN), ("key", pg.K_RETURN),
              ("screen", "Maria is ready"), ("shot", "maria-ready"), ("key", pg.K_RETURN),
              ("screen", "Game files"), ("shot", "game-files-done"),
              ("expect", lambda d: d.launcher.maria_ready(), "Maria is made"),
              ("key", pg.K_ESCAPE), ("screen", "Settings"), ("key", pg.K_ESCAPE), ("screen", "Home"),
              ("key", pg.K_DOWN), ("key", pg.K_RETURN),  # Couch co-op
              ("screen", "Press a button"),
              ("pad", 0, A), ("pad", 0, L), ("wait", 3), ("shot", "lobby-maria"), ("pad", 0, A),
              ("pad", 101, A), ("pad", 101, R), ("wait", 3), ("pad", 101, A),
              ("screen", "Name your castle"), ("pad", 0, A),  # empty: named at the game's name entry (D126)
              ("until", lambda d: d.heading == "Game"),
              ("expect", lambda d: d.launcher.characters == [2, 1], "player 1 plays Maria, player 2 Richter"),
              ("game_frames", 600), ("shot", "maria-and-richter"),
              ("key", pg.K_ESCAPE), ("screen", "Paused"), ("key", pg.K_UP), ("key", pg.K_RETURN),  # Save and go back
              ("screen", "Home"), ("key", pg.K_UP), ("key", pg.K_RETURN)]
    return steps


def hud_check(name):
    """Both games' pictures, top rows included (each HUD), are on screen as drawn: the window's
    client area (Windows: PrintWindow, under the menu bar) matches what we rendered, at the size
    we laid it out for (design/M8 §5)."""
    def check(d):
        from display import cells
        disp = d.launcher.display
        drawn = disp.screenshot()  # what we rendered, at the size SDL says the window has
        if drawn is None:
            return d.check(False, f"{name}: the window can be read back")
        from PIL import Image
        drawn = Image.frombytes("RGBA", drawn.get_size(), pygame_bytes(drawn)).convert("RGB")
        mb = d.launcher.menubar
        shown = window_image(mb.hwnd, client=True) if sys.platform == "win32" and mb.ok else drawn
        shown.save(d.out / f"hud-{name}.png")
        drawn.save(d.out / f"hud-{name}-drawn.png")
        d.shots.append(f"hud-{name}.png")
        d.check(shown.size == drawn.size, f"{name}: the window shows all {drawn.size[1]} rows we draw",
                shown=shown.size, drawn=drawn.size)
        if shown.size != drawn.size:
            return
        for k, rect in enumerate(cells(disp.layout, disp.window.size, len(disp.games))):
            if rect is None or rect.w == 0:
                continue
            top = (rect.x, rect.y, rect.right, rect.y + max(8, rect.h // 6))  # the HUD's rows
            a, b = drawn.crop(top), shown.crop(top)
            diff = sum(abs(x - y) for p, q in zip(a.getdata(), b.getdata()) for x, y in zip(p, q))
            mean = diff / max(1, a.size[0] * a.size[1] * 3)
            lit = sum(1 for p in a.getdata() if sum(p) > 150)
            d.check(mean < 8 and lit > 20, f"{name}: game {k + 1}'s top rows (its HUD) are on screen",
                    mean_diff=round(mean, 2), lit=lit)
            # ...and they're the core's own top rows: nothing of its frame is cut on the way.
            frame = disp.games[k]._last
            if frame is not None:
                core = Image.frombytes("RGB", frame.get_size(), pygame_bytes(frame, "RGB"))
                core = core.resize((rect.w, rect.h), Image.BILINEAR).crop((0, 0, rect.w, top[3] - rect.y))
                diff = sum(abs(x - y) for p, q in zip(core.getdata(), a.getdata()) for x, y in zip(p, q))
                mean = diff / max(1, a.size[0] * a.size[1] * 3)
                d.check(mean < 20, f"{name}: game {k + 1}'s top rows are the core's frame's", mean_diff=round(mean, 2))
    return ("call", check)


def pygame_bytes(surface, fmt="RGBA"):
    import pygame
    return pygame.image.tobytes(surface, fmt)


def make_starts(d):
    import pygame as pg
    if d.subtitle.startswith(("They", "There")):
        d.post_key(pg.K_DOWN)
        d.post_key(pg.K_RETURN)


def _hud(pg):
    """Both games in play (a debug start at the castle entrance: each HUD on screen), then every
    layout (two windows too), both pixel modes and three window sizes: hud_check()."""
    A = pg.CONTROLLER_BUTTON_A
    steps = [("screen", "Welcome"), ("key", pg.K_RETURN), ("screen", "Co-op disc ready"), ("key", pg.K_RETURN),
             ("screen", "Home"), ("menu", "debug_starts"),
             ("until", lambda d: d.heading == "Debug starts"),
             ("call", make_starts),                               # not made yet: Yes, make them
             ("until", lambda d: d.heading == "Debug starts" and d.subtitle.startswith("Both")),
             ("key", pg.K_DOWN), ("key", pg.K_RETURN),            # Places
             ("screen", "Places"), ("key", pg.K_RETURN),           # the first: the castle entrance
             ("screen", "Press a button"), ("pad", 0, A), ("pad", 101, A), ("pad", 0, A), ("pad", 101, A),
             ("until", lambda d: d.heading == "Game"), ("game_frames", 240)]
    for w, h in ((1032, 592), (1600, 900), (800, 1000)):
        steps += [("call", lambda d, w=w, h=h: setattr(d.launcher.display.window, "size", (w, h))), ("wait", 20)]
        for layout in ("side", "stacked", "p1", "p2", "windows", "auto"):
            steps += [("menu", f"layout:{layout}"), ("wait", 20), hud_check(f"{w}x{h}-{layout}")]
    steps += [("menu", "layout:auto"),
              ("key", pg.K_ESCAPE), ("screen", "Paused"), ("key", pg.K_UP), ("key", pg.K_RETURN),
              ("screen", "Home"), ("key", pg.K_UP), ("key", pg.K_RETURN)]
    return steps


SCRIPTS = {"couch": _couch, "solo": _solo, "test_castles": _test_castles, "startup": _startup, "characters": _characters, "hud": _hud, "perf": _perf, "window": _window, "menus": _menus,
           "online_host": lambda pg: _online_host(pg, os.environ["COOP_UX_CODE"]),
           "online_join": lambda pg: _online_join(pg, os.environ["COOP_UX_CODE"])}


def online(out, retail_cue, python=sys.executable, real_relay=False):
    """Two launchers, two data folders, one relay folder (or the real ntfy.sh): one hosts, the
    other joins."""
    tmp = Path(tempfile.mkdtemp(prefix="coop-ux-online-"))
    env = dict(os.environ, COOP_UX_CODE=str(tmp / "code.txt"))
    if not real_relay:
        env["COOP_RELAY_DIR"] = str(tmp / "relay")
    procs = []
    for role in ("host", "join"):
        e = dict(env, COOP_DATA=str(tmp / role))
        procs.append(subprocess.Popen([python, __file__, f"online_{role}", "--out", str(out / role),
                                       "--disc", str(retail_cue)], env=e))
        for _ in range(600):  # the joiner starts once the host waits in its lobby (one disc folder)
            if role == "join" or Path(env["COOP_UX_CODE"]).exists() or procs[0].poll() is not None:
                break
            time.sleep(0.2)
    codes = [p.wait(timeout=600) for p in procs]
    ok = codes == [0, 0]
    print(f"{'PASSED' if ok else 'FAILED'} online: host {codes[0]}, join {codes[1]}")
    return ok


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("script", choices=sorted(SCRIPTS) + ["online"])
    ap.add_argument("--out")
    ap.add_argument("--disc", help="the retail .cue (default: disks/sotn.us.cue)")
    ap.add_argument("--real-relay", action="store_true", help="online: meet on ntfy.sh, as players do")
    args = ap.parse_args()
    disc = Path(args.disc) if args.disc else ROOT / "disks" / "sotn.us.cue"
    out = Path(args.out) if args.out else DEFAULT_OUT / args.script
    if args.script == "online":
        sys.exit(0 if online(out, disc, real_relay=args.real_relay) else 1)
    rep = run(args.script, out, disc)
    sys.exit(0 if rep["passed"] else 1)


if __name__ == "__main__":
    main()
