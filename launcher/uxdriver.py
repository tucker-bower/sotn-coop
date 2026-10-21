"""Plays the launcher like a person would, and photographs every screen (design/M7b-polish.md).

    python launcher/uxdriver.py couch     [--out DIR]   fresh install: disc, lobby, a new game,
                                                        a controller unplugged, pause, leave
    python launcher/uxdriver.py window    [--out DIR]   every layout and pixel mode, resized,
                                                        maximized, fullscreen; frame times
    python launcher/uxdriver.py menus     [--out DIR]   every menu-bar item (Windows: through the
                                                        real menu bar's window procedure)
    python launcher/uxdriver.py online    [--out DIR]   two launchers on this PC: one hosts, the
                                                        other types the room code; both play

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


def window_image(hwnd):
    """One window as Windows draws it, frame and menu bar included (PrintWindow): never brought
    to the front, and nothing else on the screen is captured."""
    import ctypes
    from ctypes import wintypes
    from PIL import Image
    u, g = ctypes.windll.user32, ctypes.windll.gdi32
    r = wintypes.RECT()
    u.GetWindowRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    hdc = u.GetWindowDC(hwnd)
    mem = g.CreateCompatibleDC(hdc)
    bmp = g.CreateCompatibleBitmap(hdc, w, h)
    g.SelectObject(mem, bmp)
    u.PrintWindow(hwnd, mem, 2)  # PW_RENDERFULLCONTENT

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
    for f in out.glob("*.png"):
        f.unlink()
    if "COOP_DATA" not in os.environ:
        os.environ["COOP_DATA"] = tempfile.mkdtemp(prefix="coop-ux-")
    if retail_cue:
        os.environ["COOP_PICK_FILE"] = str(retail_cue)
    if not (ROOT / "bios" / "openbios.bin").exists():  # a dev checkout: the OpenBIOS the release ships
        sys.path.insert(0, str(ROOT / "harness"))
        from coop_env import ENV, path
        openbios = path(ENV["paths"]["win_emulators"]) / "PCSX-Redux" / "openbios.bin"
        if openbios.exists():
            os.environ.setdefault("COOP_DEV_BIOS", str(openbios))
    dev_patch = ROOT / ".env" / "release" / "sotn-coop.bps"
    if not (ROOT / "patcher" / "sotn-coop.bps").exists() and dev_patch.exists():
        os.environ.setdefault("COOP_PATCH", str(dev_patch))
    sys.path.insert(0, str(HERE))
    import app
    import pygame
    steps = SCRIPTS[script](pygame)
    drv = Driver(steps, out, app.Launcher)
    error = None
    try:
        launcher = app.Launcher()
        if os.environ.get("COOP_UX_NO_AUDIO"):
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
        ("screen", "Home"), ("key", pg.K_RETURN),            # Couch co-op
        ("screen", "Press a button"), ("shot", "lobby-empty"),
        ("pad", 0, A),                                      # player 1 joins (id 0, like the first real controller)
        ("pad", 101, A),                                      # player 2 joins
        ("wait", 3), ("shot", "lobby-joined"),
        ("pad", 101, B),                                      # player 2 leaves...
        ("wait", 3), ("shot", "lobby-p2-left"),
        ("pad", 101, pg.CONTROLLER_BUTTON_X),                 # ...and comes back (any button)
        ("pad", 0, A), ("wait", 2), ("shot", "lobby-p1-ready"),
        ("pad", 101, L), ("wait", 3), ("shot", "lobby-richter-locked"),  # Richter: not yet
        ("pad", 101, A),                                      # can't be ready as Richter
        ("wait", 10), ("expect", lambda d: d.heading.startswith("Press a button"), "a locked character can't be ready"),
        ("pad", 101, pg.CONTROLLER_BUTTON_DPAD_RIGHT),        # back to Alucard
        ("pad", 101, A),                                      # both ready: New game (no playthroughs yet)
        ("until", in_game), ("expect", lambda d: d.inputs <= 10, "home to playing in 10 inputs or fewer"),
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


def _window(pg):
    steps = _couch(pg, quit_at_end=False)[:-2]
    i = next(k for k, s in enumerate(steps) if s[0] == "unplug")
    steps = steps[:i]  # into the game, both playing

    for layout in ("side", "stacked", "p1", "p2", "windows", "auto"):
        for scaling in ("sharp", "smooth"):
            steps += [("menu", f"layout:{layout}"), ("menu", f"scaling:{scaling}"), ("wait", 20),
                      ("shot", f"{layout}-{scaling}")]
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
    for action in ("layout:stacked", "scaling:smooth", "netsim:wifi", "netsim:off", "layout:auto", "scaling:sharp"):
        steps += [("menu", action), ("wait", 5)]
    steps += [("expect", lambda d: d.launcher.settings.get("scaling") == "sharp" and not d.launcher.settings.get("netsim"),
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


def _online_host(pg, code_file):
    A = pg.CONTROLLER_BUTTON_A

    def write_code(d):
        room = d.launcher.room_info.split("room ")[1].split(",")[0]
        Path(code_file).write_text(room)
    return [("screen", "Welcome"), ("key", pg.K_RETURN), ("screen", "Co-op disc ready"), ("key", pg.K_RETURN),
            ("count_inputs",),
            ("screen", "Home"), ("key", pg.K_DOWN), ("key", pg.K_RETURN),
            ("screen", "Online co-op"), ("key", pg.K_RETURN),                 # Host: new game
            ("screen", "Press a button"), ("call", write_code), ("shot", "host-waiting"),
            ("pad", 100, A), ("pad", 100, A),
            ("until", lambda d: d.heading == "Game"), ("game_frames", 900), ("shot", "host-playing"),
            ("expect", lambda d: "Partner connected" in d.launcher.display._bar_key[0][0], "the host sees its partner connected"),
            ("key", pg.K_ESCAPE), ("screen", "Paused"), ("key", pg.K_UP), ("key", pg.K_RETURN),
            ("screen", "Online co-op"), ("key", pg.K_ESCAPE), ("screen", "Home"), ("menu", "quit")]


def _online_join(pg, code_file):
    A = pg.CONTROLLER_BUTTON_A
    return [("screen", "Welcome"), ("key", pg.K_RETURN), ("screen", "Co-op disc ready"), ("key", pg.K_RETURN),
            ("count_inputs",),
            ("screen", "Home"), ("key", pg.K_DOWN), ("key", pg.K_RETURN),
            ("screen", "Online co-op"), ("key", pg.K_DOWN), ("key", pg.K_RETURN),  # Join your partner
            ("screen", "Join your partner"),
            *[("key", pg.K_BACKSPACE)] * 24,  # the box starts with the clipboard (here: the host's code)
            ("type_file", code_file), ("key", pg.K_RETURN),
            ("screen", "Press a button"), ("shot", "join-lobby"),
            ("pad", 200, A), ("pad", 200, A),
            ("until", lambda d: d.heading == "Game"), ("game_frames", 900), ("shot", "join-playing"),
            ("expect", lambda d: "Partner connected" in d.launcher.display._bar_key[0][0], "the joiner sees its partner connected"),
            ("key", pg.K_ESCAPE), ("screen", "Paused"), ("key", pg.K_UP), ("key", pg.K_RETURN),
            ("screen", "Online co-op"), ("key", pg.K_ESCAPE), ("screen", "Home"), ("menu", "quit")]


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


SCRIPTS = {"couch": _couch, "perf": _perf, "window": _window, "menus": _menus,
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
