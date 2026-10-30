"""SOTN Co-op: the player's launcher (design/M6-playable-build.md, design/M7b-polish.md).

    python launcher/app.py

First run: your disc image, once. Then: Solo, Couch co-op or Online co-op, each on a castle
(design/M11: a playthrough anyone can continue; a joiner keeps a copy of the host's).
- Couch: one lobby screen where each player presses a button on their controller to join and
  picks a character, then the castle.
- Online: Host (pick a castle; you get a room code to give your partner) or Join (you type theirs).
Menus work with a controller (d-pad, cross/A = OK, circle/B = back), the keyboard (arrows,
Enter, Esc) or the mouse. On Windows the window also has a menu bar (launcher/winmenu.py), and
it can be resized, maximized and made fullscreen (F11), with the games laid out side by side,
stacked, or in two windows (launcher/display.py).
"""

import logging
import math
import multiprocessing
import os
import shutil
import sys
import tempfile
import threading
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
for sub in ("launcher", "harness", "patcher", ""):
    sys.path.insert(0, str(APP / sub) if sub else str(APP))

import paths  # noqa: E402
from platform_android import ANDROID  # noqa: E402

if sys.platform == "win32":
    # pygame's DLLs (libpng: the icon) are loaded by name, later. Windows looks through PATH,
    # and a process started by the installer refuses to walk past reparse points there
    # (RedirectionGuard: "untrusted mount point"). pygame's folder first finds them at once.
    import importlib.util
    spec = importlib.util.find_spec("pygame")
    if spec and spec.origin:
        os.environ["PATH"] = os.path.dirname(spec.origin) + os.pathsep + os.environ.get("PATH", "")

if sys.stderr is None:  # pythonw (the Start menu shortcut): no console. Errors go to a file.
    sys.stderr = open(paths.data_dir() / "launcher-errors.log", "a", buffering=1, encoding="utf-8")
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")

import pygame  # noqa: E402

from display import CANVAS, LAYOUT_NAMES, Display  # noqa: E402
from paths import human, load_settings, save_settings  # noqa: E402
from report import VERSION  # noqa: E402
from winmenu import MENU_EVENT, WinMenu  # noqa: E402

TITLE = "Castlevania: Symphony of the Night  —  Co-op"
WINDOW_TITLE = "SOTN Co-op"
SIZE = CANVAS
INK, DIM, GOLD, BLOOD, BG = (230, 225, 215), (150, 145, 140), (240, 205, 120), (150, 20, 30), (12, 8, 14)
OK_GREEN = (140, 200, 120)
# OpenBIOS built with FASTBOOT (scripts/bootstrap.sh): the game starts 5 s sooner than on
# PCSX-Redux's standard build, which stays for savestates made before 0.12 (M12 v1.0)
BUNDLED_BIOS = APP / "bios" / "openbios-fast.bin"
LEGACY_BIOS = APP / "bios" / "openbios.bin"
PATCH = Path(os.environ.get("COOP_PATCH") or APP / "patcher" / "sotn-coop.bps")  # COOP_PATCH: dev checkouts
# Maria's patches (maria/make_patches.py): the installer's, or a dev checkout's build.
MARIA_PATCHES = next((d for d in (APP / "patcher" / "maria", APP / ".env" / "out" / "maria")
                      if (d / "maria.json").exists()), APP / "patcher" / "maria")
CHARACTERS = ("Alucard", "Richter", "Maria")  # index = CHAR_* (module/link.h)
# Alucard's spells for the right stick (design/M8b §3.2): SpellIds, None = nothing there.
SPELL_CHOICES = (None, 0, 1, 2, 3, 5, 7)
DEFAULT_SPELLS = [2, 5, 3, 0]  # up Hellfire, right Soul Steal, down Tetra Spirit, left Dark Metamorphosis
STICK = ("↑", "→", "↓", "←")

log = logging.getLogger("launcher")

HELP_PLAY = """Each of you plays your own game, on your own half of the window.
Whatever one of you finds (relics, items, gold, the map) the other gets too, at once.
Meet in the same room to fight the same enemies. Bosses pull you both in.

Controls: your controller, as on a PlayStation. Keyboard: Controllers › Keyboard keys.
Your partner's map cursor is blue. On the map, press Cross to teleport to your partner.
Save at a coffin: it saves both games. Continue loads both.

Castles: every game is a castle, with the name you give it when you start it (or the name you type
in the game) and when it began (Tucker_2026-10-25-21:40). Play any castle solo, on the couch, or host it online with anyone.
Whoever joins you online keeps a copy of your castle, to play solo or host later.
Level is shared: a kill's XP goes to both of you, at half (solo: all of it). Solo bosses have
their normal HP.

Characters: pick Alucard, Richter or Maria in the lobby (Maria needs your Dracula X Chronicles
disc: Settings › Game files). Richter and Maria learn their moves from Alucard's relics: Leap Stone
for the second jump, Gravity Boots for the high jump, Soul of Wolf for the slide, Form of Mist to
pass through grates (keep walking into them), Echo of Bat for item crashes. They level up and wear
Alucard's armor (Start: the equipment menu).
Shortcuts (each player's own, Triangle / Y on your lobby card): Richter and Maria high-jump with
L2 and blade-dash with R2. Alucard casts the spells he knows with the right stick
(Settings › Controls picks which).

Esc (or the Game menu) pauses. F9 saves a bug report: please send it to us."""

HELP_ONLINE = """Hosting: you get a room code like BAT-7K2Q. Read it to your partner, or paste it to them.
Joining: type your partner's room code. Both of you need the same version of SOTN Co-op.

If it can't connect (only one of you needs to fix it):
·  Windows may ask whether to allow SOTN Co-op through its firewall: choose Allow.
·  Turn on UPnP in your router's settings (most routers have it on already). The game then opens
   its own port.
·  A phone hotspot, or some internet providers, can't connect directly. Try another network.
·  Or forward UDP port 47811 on your router to your PC or phone.
·  Still stuck? Forward the port on the host's router; the joiner then types the host's address as
   ip:port instead of the room code (Help › About shows the port while hosting).
The status bar shows the ping. Under 150 ms plays great; up to 300 ms is fine."""

KEYS_HELP = """Player 1:  arrows to move.  Z Cross,  X Square,  C Circle,  V Triangle,  A L1,  S R1,
               D L2,  W R2,  Enter Start,  Right Shift Select.  Keypad 8 6 2 4: the right stick.
Player 2:  I J K L to move.  F Cross,  G Square,  H Circle,  T Triangle,  Q L1,  E R1,
               R L2,  Y R2,  Space Start,  Tab Select.

Esc: pause.   F9: report a problem.   F11: fullscreen.   F1 (couch): which game plays the music."""


class Navigate(Exception):
    """A menu-bar item that goes somewhere (New game, Savestates, ...): back to the top, there."""

    def __init__(self, action):
        super().__init__(action)
        self.action = action


class ConnectFailed(Exception):
    pass


class UI:
    """Drawing (on the display's canvas) and input for the menus."""

    def __init__(self, display, on_action):
        self.display = display
        self.screen = display.canvas
        self.on_action = on_action  # menu-bar items that don't go anywhere (View, Help...)
        self.title = pygame.font.SysFont("georgia", 34, bold=True)
        self.big = pygame.font.SysFont("georgia", 26)
        self.small = pygame.font.SysFont("georgia", 17)
        self.mono = pygame.font.SysFont("consolas", 14)
        self._rects = []
        self.pads = None  # gameview.Pads, once the launcher has made it

    def events(self, raw=False):
        """Menu actions this frame: "up", "down", "left", "right", "ok", "back", "quit",
        ("pad", id), ("click", index) and ("hover", index). raw: also ("event", ev) for each."""
        out = []
        for ev in pygame.event.get():
            if raw:
                out.append(("event", ev))
            if self.display.handle(ev):
                continue
            if ev.type in (pygame.QUIT, pygame.WINDOWCLOSE):
                out.append("quit")
            elif ev.type == MENU_EVENT:
                if self.on_action(ev.action) is False:
                    raise Navigate(ev.action)
            elif ev.type == pygame.KEYDOWN:
                a = {pygame.K_UP: "up", pygame.K_DOWN: "down", pygame.K_LEFT: "left", pygame.K_RIGHT: "right",
                     pygame.K_RETURN: "ok", pygame.K_SPACE: "ok", pygame.K_ESCAPE: "back", pygame.K_AC_BACK: "back"}.get(ev.key)
                if a:
                    out.append(a)
            elif ev.type == pygame.CONTROLLERBUTTONDOWN:
                a = {pygame.CONTROLLER_BUTTON_DPAD_UP: "up", pygame.CONTROLLER_BUTTON_DPAD_DOWN: "down",
                     pygame.CONTROLLER_BUTTON_DPAD_LEFT: "left", pygame.CONTROLLER_BUTTON_DPAD_RIGHT: "right",
                     pygame.CONTROLLER_BUTTON_A: "ok", pygame.CONTROLLER_BUTTON_START: "ok",
                     pygame.CONTROLLER_BUTTON_B: "back"}.get(ev.button)
                out.append(("pad", ev.instance_id))
                if a:
                    out.append(a)
            elif ev.type in (pygame.CONTROLLERDEVICEADDED, pygame.CONTROLLERDEVICEREMOVED):
                # Pads keeps every plugged-in controller open: one opened here and dropped closes
                # again, and sends no buttons. (A DualSense on Windows drops out about 0.5 s after
                # start and comes back as a new device about 7 s later.)
                if self.pads:
                    self.pads.refresh()
            elif ev.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN):
                pos = self.display.to_canvas(ev.pos)
                hit = next((k for k, r in self._rects if pos and r.collidepoint(pos)), None)
                if hit is not None:
                    out.append(("click" if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 else "hover", hit))
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3:
                    out.append("back")
        return out

    def flip(self, over_games=False):
        self.display.present(over_games)

    def frame(self, heading, subtitle=""):
        s = self.screen
        s.fill(BG)
        for y in range(0, SIZE[1], 4):  # a faint gradient, blood red at the top
            shade = max(0, 40 - y // 8)
            pygame.draw.line(s, (12 + shade, 8, 14), (0, y), (SIZE[0], y), 4)
        t = self.title.render(TITLE, True, GOLD)
        s.blit(t, ((SIZE[0] - t.get_width()) // 2, 24))
        pygame.draw.line(s, BLOOD, (120, 76), (SIZE[0] - 120, 76), 2)
        if heading:
            h = self.big.render(heading, True, INK)
            s.blit(h, ((SIZE[0] - h.get_width()) // 2, 92))
        if subtitle:
            for k, line in enumerate(self.wrap(subtitle, self.small, SIZE[0] - 120)):
                t = self.small.render(line, True, DIM)
                s.blit(t, ((SIZE[0] - t.get_width()) // 2, 128 + k * 22))
        self._rects = []

    @staticmethod
    def wrap(text, font, width):
        """text's lines, each broken at spaces to fit width."""
        out = []
        for para in text.split("\n"):
            line = ""
            for word in para.split(" "):
                trial = f"{line} {word}" if line else word
                if line and font.size(trial)[0] > width:
                    out.append(line)
                    line = word
                else:
                    line = trial
            out.append(line)
        return out

    def items(self, items, sel, top=200, hero=False):
        """hero: the first item is the big button (Couch co-op / Continue)."""
        y = top
        self._rects = []
        rest = [label for k, (label, _) in enumerate(items) if not (hero and k == 0)]
        widest = max((self.big.size("›  " + label)[0] for label in rest), default=0)
        left = max(20, (SIZE[0] - widest) // 2)
        rows = max(1, (SIZE[1] - 100 - top) // 38)  # long lists scroll with the selection
        first = 0 if hero or len(items) <= rows else min(max(0, sel - rows // 2), len(items) - rows)
        if first:
            t = self.small.render("more above", True, DIM)
            self.screen.blit(t, (left, y - 24))
        for k, (label, hint) in enumerate(items):
            if not hero and not first <= k < first + rows:
                if k == first + rows:
                    t = self.small.render("more below", True, DIM)
                    self.screen.blit(t, (left, y))
                continue
            color = GOLD if k == sel else INK
            if hero and k == 0:
                t = self.title.render(label, True, color)
                box = pygame.Rect(0, 0, max(t.get_width() + 60, 420), t.get_height() + 24)
                box.center = (SIZE[0] // 2, y + box.height // 2)
                pygame.draw.rect(self.screen, (60, 10, 18) if k == sel else (30, 14, 20), box, border_radius=8)
                pygame.draw.rect(self.screen, GOLD if k == sel else DIM, box, 2, border_radius=8)
                self.screen.blit(t, t.get_rect(center=box.center))
                self._rects.append((k, box))
                y += box.height + 22
                if k == sel and hint:
                    h = self.small.render(hint, True, DIM)
                    self.screen.blit(h, ((SIZE[0] - h.get_width()) // 2, SIZE[1] - 64))
                continue
            t = self.big.render(("›  " if k == sel else "   ") + label, True, color)
            self.screen.blit(t, (left, y))
            self._rects.append((k, pygame.Rect(left, y, max(widest, t.get_width()), 34)))
            y += 38
            if k == sel and hint:
                h = self.small.render(hint, True, DIM)
                self.screen.blit(h, ((SIZE[0] - h.get_width()) // 2, SIZE[1] - 64))

    def footer(self, text):
        t = self.mono.render(text, True, DIM)
        self.screen.blit(t, ((SIZE[0] - t.get_width()) // 2, SIZE[1] - 30))

    def bar(self, done, total, y=280):
        """Progress: a vial of blood filling up, with the percentage beside it."""
        s, frac = self.screen, max(0.0, min(1.0, done / max(total, 1)))
        t = pygame.time.get_ticks() / 1000
        cx, bw, bh = SIZE[0] // 2, 79, 168  # odd widths: centred on column cx
        body = pygame.Rect(cx - bw // 2, y + 30, bw, bh)
        # the blood, clipped to the body below its level, with a gently moving surface
        level = body.bottom - 4 - int((bh - 8) * frac)
        if frac > 0:
            s.set_clip(body.inflate(-8, -8))
            pygame.draw.rect(s, BLOOD, body.inflate(-8, -8), border_radius=24)
            wave = [(x, level + 3 * math.sin(x / 9 + t * 3)) for x in range(body.left, body.right + 1, 4)]
            pygame.draw.polygon(s, BG, [(body.left, body.top)] + wave + [(body.right, body.top)])
            pygame.draw.lines(s, (200, 40, 50), False, wave, 2)  # the surface catches the light
            for i in range(4):  # bubbles rising through it
                by = body.bottom - 8 - ((t * 22 + i * 37) % max(1, body.bottom - 8 - level))
                pygame.draw.circle(s, (190, 50, 60), (body.left + 16 + i * 11 % (bw - 28), int(by)), 2)
            s.set_clip(None)
        # the glass: body, neck and cork, and a highlight down its side
        pygame.draw.rect(s, DIM, body, 2, border_radius=28)
        neck = pygame.Rect(cx - 13, y + 12, 26, 20)
        pygame.draw.rect(s, BG, neck.inflate(-4, 4))
        pygame.draw.line(s, DIM, neck.topleft, (neck.left, neck.bottom + 1), 2)
        # a 2-px line draws right of its x: the right side at right - 1 keeps the neck centred
        pygame.draw.line(s, DIM, (neck.right - 1, neck.top), (neck.right - 1, neck.bottom + 1), 2)
        pygame.draw.rect(s, (110, 72, 44), (cx - 17, y, 35, 14), border_radius=3)
        pygame.draw.line(s, (235, 230, 225), (body.left + 12, body.top + 18), (body.left + 12, body.bottom - 26), 2)
        pct = self.small.render(f"{int(frac * 100)}%", True, DIM)
        s.blit(pct, (body.right + 18, body.centery - pct.get_height() // 2))

    def menu(self, heading, items, subtitle="", footer="", hero=False, sel=0):
        """Returns the chosen index, or None (back)."""
        while True:
            for a in self.events():
                if a == "quit":
                    raise SystemExit
                if a == "up":
                    sel = (sel - 1) % len(items)
                elif a == "down":
                    sel = (sel + 1) % len(items)
                elif a == "ok":
                    return sel
                elif a == "back":
                    return None
                elif isinstance(a, tuple) and a[0] == "hover":
                    sel = a[1]
                elif isinstance(a, tuple) and a[0] == "click":
                    return a[1]
            self.frame(heading, subtitle)
            lines = len(self.wrap(subtitle, self.small, SIZE[0] - 120)) if subtitle else 0
            self.items(items, sel, top=(130 if hero else 200) + 22 * max(0, lines - 1), hero=hero)
            if footer:
                self.footer(footer)
            self.flip()
            pygame.time.wait(16)

    def message(self, heading, text, button="OK"):
        self.menu(heading, [(button, "")], text)

    def page(self, heading, text):
        """A page of text (help), then OK."""
        lines = text.split("\n")
        while True:
            for a in self.events():
                if a == "quit":
                    raise SystemExit
                if a in ("ok", "back") or (isinstance(a, tuple) and a[0] == "click"):
                    return
            self.frame(heading)
            for k, line in enumerate(lines):
                t = self.small.render(line, True, INK)
                self.screen.blit(t, (90, 140 + k * 24))
            self.items([("OK", "")], 0, top=SIZE[1] - 80)
            self.flip()
            pygame.time.wait(16)

    def confirm(self, heading, text, yes="Yes", no="No"):
        return self.menu(heading, [(no, ""), (yes, "")], text) == 1

    def wait_for(self, heading, text, task):
        """Runs task(progress) in a thread, with a progress bar; returns its result or raises."""
        state = {"done": 0, "total": 1, "result": None, "error": None, "finished": False}

        def progress(done, total):
            state["done"], state["total"] = done, total

        def work():
            try:
                state["result"] = task(progress)
            except Exception as e:  # noqa: BLE001 - shown to the player
                state["error"] = e
            state["finished"] = True

        threading.Thread(target=work, daemon=True).start()
        while not state["finished"]:
            if "quit" in self.events():
                raise SystemExit
            self.frame(heading, text)
            self.bar(state["done"], state["total"])
            self.flip()
            pygame.time.wait(30)
        if state["error"]:
            raise state["error"]
        return state["result"]


def _pick_file_windows(title, types):
    """Windows' own Open dialog (comdlg32), through ctypes: the bundled Python has no tkinter."""
    import ctypes
    from ctypes import wintypes

    class OFN(ctypes.Structure):
        _fields_ = [("lStructSize", wintypes.DWORD), ("hwndOwner", wintypes.HWND), ("hInstance", wintypes.HINSTANCE),
                    ("lpstrFilter", wintypes.LPCWSTR), ("lpstrCustomFilter", wintypes.LPWSTR),
                    ("nMaxCustFilter", wintypes.DWORD), ("nFilterIndex", wintypes.DWORD), ("lpstrFile", wintypes.LPWSTR),
                    ("nMaxFile", wintypes.DWORD), ("lpstrFileTitle", wintypes.LPWSTR), ("nMaxFileTitle", wintypes.DWORD),
                    ("lpstrInitialDir", wintypes.LPCWSTR), ("lpstrTitle", wintypes.LPCWSTR), ("Flags", wintypes.DWORD),
                    ("nFileOffset", wintypes.WORD), ("nFileExtension", wintypes.WORD), ("lpstrDefExt", wintypes.LPCWSTR),
                    ("lCustData", wintypes.LPARAM), ("lpfnHook", ctypes.c_void_p), ("lpTemplateName", wintypes.LPCWSTR),
                    ("pvReserved", ctypes.c_void_p), ("dwReserved", wintypes.DWORD), ("FlagsEx", wintypes.DWORD)]

    filt = "".join(f"{name} ({pattern})\0{pattern.replace(' ', ';')}\0" for name, pattern in types) + "\0"
    buf = ctypes.create_unicode_buffer(1024)
    ofn = OFN()
    ofn.lStructSize = ctypes.sizeof(OFN)
    ofn.lpstrFilter = filt
    ofn.lpstrFile = ctypes.cast(buf, wintypes.LPWSTR)
    ofn.nMaxFile = 1024
    ofn.lpstrTitle = title
    ofn.Flags = 0x00001000 | 0x00000800 | 0x00080000  # file must exist, path must exist, explorer
    if ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn)):
        return Path(buf.value)
    return None


def pick_file(title, types, ui=None, android_disc=None):
    """The system's file picker: Windows' own dialog, or tkinter elsewhere. On Android, ui shows
    the copy into the app, and android_disc picks SOTN's disc: "folder" (the folder it's in) or
    "files" (its files one by one)."""
    if os.environ.get("COOP_PICK_FILE"):  # tests (launcher/uxdriver.py)
        return Path(os.environ["COOP_PICK_FILE"])
    if ANDROID:  # the system's picker: the files are copied into the app's folder (design/M9)
        import patcher
        import platform_android
        try:
            run = ui and (lambda task: ui.wait_for("Copying your disc", "Into the app, once. This takes a minute.", task))
            if android_disc == "files":
                return platform_android.pick_disc_files(title, paths.data_dir() / "discs", run)
            if android_disc == "folder":  # one tap, any rip, in folders inside it too
                return platform_android.pick_disc(title, paths.data_dir() / "discs", run)
            got = platform_android.pick_files(title, paths.data_dir() / "discs", run)
        except (patcher.DiscError, OSError):  # said to the player
            raise
        except Exception:  # noqa: BLE001
            log.exception("file picker")
            return None
        cues = [p for p in got if p.suffix.lower() == ".cue"]
        return (cues or got or [None])[0]
    if sys.platform == "win32":
        try:
            return _pick_file_windows(title, types)
        except Exception:  # noqa: BLE001
            log.exception("file picker")
    try:
        import tkinter
        from tkinter import filedialog
        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(title=title, filetypes=types)
        root.destroy()
        return Path(path) if path else None
    except Exception:  # noqa: BLE001
        log.exception("file picker")
        return None


class Launcher:
    def __init__(self):
        pygame.init()
        self.settings = load_settings()
        # Each seat's character (CHAR_*, design/M8): picked in the lobby, remembered.
        self.characters = [c if 0 <= c < len(CHARACTERS) and self.playable(c) else 0
                           for c in (list(self.settings.get("characters") or []) + [0, 0])[:2]]
        self.display = Display(self.settings, WINDOW_TITLE)
        self.menubar = WinMenu(WINDOW_TITLE)
        self.menubar.update(self.settings)
        self.display.on_fullscreen.append(lambda fs: self.menubar.show(not fs))
        self.ui = UI(self.display, self.action)
        self.screen = self.display.canvas
        from gameview import Pads
        self.pads = Pads((None, None))
        self.ui.pads = self.pads
        self.audio = None
        self.room_info = ""  # while hosting: the port, for Help › About
        try:
            from gameview import Audio
            self.audio = Audio()
        except Exception:  # noqa: BLE001 - no sound device: play silent
            log.exception("audio")

    # --- the menu bar's items that don't go anywhere (the rest raise Navigate)

    def action(self, action):
        """Handles a menu-bar item where it stands. False: it goes somewhere (Navigate)."""
        st = self.settings
        if action.startswith("layout:"):
            st["layout"] = action.split(":", 1)[1]
        elif action.startswith("netsim:"):
            st["netsim"] = None if action.endswith("off") else action.split(":", 1)[1]
        elif action == "fullscreen":
            self.display.toggle_fullscreen()
        elif action == "data_folder":
            paths.open_folder(paths.data_dir())
        elif action == "open_log":
            paths.open_folder(paths.data_dir() / "launcher.log")
        elif action == "help_play":
            self.ui.page("How to play", HELP_PLAY)
        elif action == "help_online":
            self.ui.page("Online troubleshooting", HELP_ONLINE)
        elif action == "keys":
            self.ui.page("Keyboard keys", KEYS_HELP)
        elif action == "about":
            from report import VERSION
            from link.transport import WIRE_VERSION
            self.ui.page("About SOTN Co-op",
                         f"Version {VERSION} (link protocol {WIRE_VERSION}).\n"
                         "A co-op mod of Castlevania: Symphony of the Night, built on sotn-decomp.\n"
                         "No game data is included: the co-op disc is made from your own.\n"
                         f"Your saves and bug reports: {paths.data_dir()}\n{self.room_info}")
        elif action in ("pause", "report", "leave"):
            pass  # these only mean something in a game (gameview.py)
        else:
            return False
        save_settings(st)
        self.menubar.update(st)
        return True

    # --- the environment the games run in

    def bios(self):
        b = self.settings.get("bios") or (None if BUNDLED_BIOS.exists() else os.environ.get("COOP_DEV_BIOS"))
        return Path(b) if b and Path(b).exists() else BUNDLED_BIOS

    def apply_bios(self, bios=None):
        os.environ["COOP_BIOS"] = str(bios or self.bios())

    def disc(self):
        d = self.settings.get("disc")
        return Path(d) if d and Path(d).exists() else None

    # --- characters (design/M8)

    def maria_blob_path(self):
        return paths.characters_dir() / "maria.blob"

    def maria_ready(self):
        """Maria is made (from the player's DXC disc) for this version's patches. A newer launcher
        remakes her from the disc it remembers, quietly."""
        blob, about = self.maria_blob_path(), MARIA_PATCHES / "maria.json"
        if not about.exists():
            return False
        if blob.exists() and blob.stat().st_mtime >= about.stat().st_mtime:
            return True
        iso = self.settings.get("dxc_iso")
        if iso and Path(iso).exists():
            import characters
            try:
                characters.maria_blob(iso, MARIA_PATCHES, blob)
                return True
            except characters.DiscError:
                log.exception("remaking Maria")
        return False

    # --- each player's button shortcuts (design/M8b §3.2): on or off per seat, remembered

    def shortcuts(self, seat):
        return bool((self.settings.get("shortcuts") or [True, True])[seat])

    def set_shortcuts(self, seat, on):
        v = list(self.settings.get("shortcuts") or [True, True])
        v[seat] = on
        self.settings["shortcuts"] = v
        save_settings(self.settings)

    def spells(self, seat):
        v = (self.settings.get("spells") or [DEFAULT_SPELLS, DEFAULT_SPELLS])[seat]
        return list(v) if len(v) == 4 else list(DEFAULT_SPELLS)

    def options(self, seat):
        """The OPT_* bits for that seat's game (link/mailbox.py)."""
        from link.mailbox import OPT_SHORTCUTS, spell_options
        return (OPT_SHORTCUTS if self.shortcuts(seat) else 0) | spell_options(self.spells(seat))

    def controls_menu(self):
        """Settings › Controls: each player's shortcuts, and Alucard's spells on the right stick."""
        from link.mailbox import SPELLS
        ui, sel = self.ui, 0
        while True:
            items = []
            for seat in (0, 1):
                items.append((f"Player {seat + 1} shortcuts: {'On' if self.shortcuts(seat) else 'Off'}",
                              "Richter and Maria: L2 high jump, R2 blade dash. Alucard: spells on the right stick. "
                              "Off: the original controls only."))
                for d, spell in enumerate(self.spells(seat)):
                    items.append((f"Player {seat + 1} right stick {STICK[d]}: {SPELLS[spell] if spell is not None else 'Nothing'}",
                                  "Alucard casts it if he knows the spell and has the MP"))
            k = ui.menu("Controls", items, footer="Also on each player's card in the lobby: Triangle / Y")
            if k is None:
                return
            sel = k
            seat, row = divmod(k, 5)
            if row == 0:
                self.set_shortcuts(seat, not self.shortcuts(seat))
            else:
                spells = [list(self.spells(0)), list(self.spells(1))]
                cur = spells[seat][row - 1]
                spells[seat][row - 1] = SPELL_CHOICES[(SPELL_CHOICES.index(cur) + 1) % len(SPELL_CHOICES)] \
                    if cur in SPELL_CHOICES else None
                self.settings["spells"] = spells
                save_settings(self.settings)

    def playable(self, character):
        return character != 2 or self.maria_ready()

    def blob(self):
        """Maria's blob for every game when she's made: a partner who plays her is drawn from it."""
        return self.maria_blob_path().read_bytes() if self.maria_ready() else None

    def add_dxc(self):
        """Settings › Game files: the player points at their Dracula X Chronicles .iso."""
        import characters
        try:
            path = pick_file("Your Castlevania: The Dracula X Chronicles disc image (.iso)",
                             [("PSP disc image", "*.iso *.ISO"), ("All", "*.*")], self.ui)
        except OSError as e:  # copying it into the app (Android): most likely a full phone
            log.exception("copying the DXC disc")
            self.ui.message("Couldn't copy your disc", f"{e.strerror or e}.\nThe app needs about 2 GB free for it.")
            return
        if not path:
            return
        try:
            self.ui.wait_for("Adding Maria", f"From {path.name}\nThis takes a few seconds.",
                             lambda progress: characters.maria_blob(path, MARIA_PATCHES, self.maria_blob_path()))
        except characters.DiscError as e:
            self.ui.message("That disc won't work", str(e))
            return
        self.settings["dxc_iso"] = str(path)
        save_settings(self.settings)
        self.ui.message("Maria is ready", "Pick her in the lobby, as either player.")

    def game_files(self):
        ui = self.ui
        while True:
            disc, iso = self.disc(), self.settings.get("dxc_iso")
            bios = "OpenBIOS (free, built in). Your own BIOS works too." if self.bios() == BUNDLED_BIOS \
                else f"Your BIOS: {self.bios().name}"
            k = ui.menu("Game files", [
                (f"Symphony of the Night (PS1, USA):  required, {'set' if disc else 'not set'}",
                 f"{disc.name if disc else 'Not chosen'}   (choose again)"),
                (f"Dracula X Chronicles (PSP, USA):  optional, {'Maria added' if self.maria_ready() else 'adds Maria'}",
                 (Path(iso).name + "   (choose again)") if iso and self.maria_ready()
                 else "Adds Maria as a playable character. Choose your .iso"),
                ("PlayStation BIOS:  included", bios + "   (change)")],
                "Only the Symphony of the Night disc is needed to play.")
            if k is None:
                return
            if k == 0:
                self.settings["disc"] = None
                save_settings(self.settings)
                self.wizard()
            elif k == 1:
                self.add_dxc()
            elif k == 2:
                self.choose_bios()

    def starts_dir(self):
        return paths.debug_starts_dir() / f"{self.disc().stem}@{self.bios().stem}"

    def patch_crc(self):
        import json
        manifest = APP / "patcher" / "manifest.json"
        if manifest.exists():
            try:
                return int(json.loads(manifest.read_text())["target_crc32"], 16)
            except Exception:  # noqa: BLE001
                return None
        return None

    # --- first run

    def update_disc(self):
        """After an update, remakes the co-op disc from the player's own disc for this version's
        patch, once. An old one would play a different game from the partner's, who'd be told
        it's the same (HELO carries this version's patch CRC)."""
        want = self.patch_crc()
        if not self.disc() or want is None or self.settings.get("disc_patch") == want:
            return
        import patcher
        src = self.settings.get("disc_source")
        if not src:  # made before 0.9.0: the player's disc is next to it, named as it was
            coop = self.disc()
            stem = coop.name.replace(" (Co-op).cue", "")
            src = next((p for p in (coop.with_name(stem + ".cue"), coop.with_name(stem + ".bin"),
                                    coop.with_name(stem + " (Track 1).bin")) if p.exists()), coop.with_name(stem + ".cue"))
        src = Path(src)
        try:
            cue = self.ui.wait_for("Updating the co-op disc",
                                   f"This version of SOTN Co-op changes the co-op disc: it's remade\nfrom {src.name}, once.",
                                   lambda progress: patcher.apply(src, PATCH, progress=progress))
        except (patcher.DiscError, patcher.bps.PatchError, OSError) as e:
            log.warning("updating the co-op disc from %s: %s", src, e)
            self.settings["disc"] = None
            save_settings(self.settings)
            self.ui.message("Your disc again, please", f"This version of SOTN Co-op remakes the co-op disc, and couldn't\n"
                            f"from {src.name}: {e}\nChoose your disc image again.")
            return
        self.settings.update(disc=str(cue), disc_source=str(src), disc_patch=want)
        save_settings(self.settings)

    def wizard(self):
        ui = self.ui
        self.update_disc()
        while not self.disc():
            if ANDROID:  # the folder picker: Android can't see the .bin files next to a .cue
                choice = ui.menu("Welcome", [("Choose my disc's folder", "The folder with your .cue and .bin files (or a .zip of them)"),
                                             ("Pick the files instead", "Not in a folder of their own? Pick the .cue and .bin files together, or the .zip"),
                                             ("Quit", "")],
                                 "Co-op is made from your own copy of the game: a disc image of\n"
                                 "Castlevania: Symphony of the Night, USA version (SLUS-00067), as .cue + .bin.\n"
                                 "Pick the folder it's in, then Use this folder. It's copied into the app.")
            else:
                choice = ui.menu("Welcome", [("Choose my disc image", "Your own Symphony of the Night (USA) rip: the .cue file"),
                                             ("Quit", "")],
                                 "Co-op is made from your own copy of the game: a disc image of\n"
                                 "Castlevania: Symphony of the Night, USA version (SLUS-00067), as .cue + .bin.\n"
                                 "Your file is never changed: the co-op disc is made next to it.")
            if choice not in ((0, 1) if ANDROID else (0,)):
                raise SystemExit
            import patcher
            try:
                path = pick_file("Your Symphony of the Night disc image (.cue)", [("Disc image", "*.cue *.bin"), ("All", "*.*")],
                                 ui, android_disc=("folder", "files")[choice])
            except patcher.DiscError as e:
                ui.message("No disc image there", str(e))
                continue
            except OSError as e:  # copying it into the app (Android): most likely a full phone
                log.exception("copying the disc")
                ui.message("Couldn't copy your disc", f"{e.strerror or e}.\nThe app needs about 1.3 GB free for your disc and its co-op version.")
                continue
            if not path:
                continue
            try:
                cue = ui.wait_for("Making the co-op disc", f"From {path.name}\nThis takes a few seconds.",
                                  lambda progress: patcher.apply(path, PATCH, progress=progress))
            except (patcher.DiscError, patcher.bps.PatchError) as e:
                if ANDROID:  # the copy we made of it: no use, and it's big
                    shutil.rmtree(paths.data_dir() / "discs", ignore_errors=True)
                ui.message("That disc won't work", str(e))
                continue
            self.settings.update(disc=str(cue), disc_source=str(path), disc_patch=self.patch_crc())
            save_settings(self.settings)
            ui.message("Co-op disc ready", "Your disc is set up in the app: you can delete your copy\nfrom the phone's folder now."
                       if ANDROID else f"Made {cue.name}\nnext to your disc image.")

    def install_test_castles(self):
        """The test castles, from the debug starts' joint saves (made with them: debugstarts.py)."""
        import debugstarts
        from archive import Castle
        for name, v in debugstarts.load(self.starts_dir(), self.patch_crc()).items():
            if v.get("save") and (self.starts_dir() / v["save"]).exists():
                Castle.make_test(name, (self.starts_dir() / v["save"]).read_bytes(), v["start"], v["order"], v["about"])

    def make_debug_starts(self):
        import debugstarts
        self.apply_bios()
        proc, queue = debugstarts.start(self.disc(), self.starts_dir(), self.patch_crc())
        text, done, total = "Starting", 0, 1
        while True:
            while not queue.empty():
                kind, done, total, text = queue.get()
                if kind == "error":
                    log.error("debug starts: %s", text)
                    self.ui.message("Couldn't make the debug starts", text.split("\n")[0] +
                                    "\nThe game works without them; they're for testing.")
                    return
                if kind == "done":
                    self.install_test_castles()
                    return
            if "quit" in self.ui.events():
                proc.terminate()
                raise SystemExit
            self.ui.frame("Making the debug starts",
                          "Savestates to start anywhere on the route, for testing and bug reports.\n"
                          f"Made from your disc, once. {text}...")
            self.ui.bar(done, total)
            self.ui.flip()
            pygame.time.wait(30)

    # --- the lobby: who plays with which controller, and as whom

    def lobby(self, slots=2, online=None, subtitle=""):
        """Players join by pressing a button on their controller (or Enter on the keyboard), pick
        a character, and press ✕ / A when ready. Returns each player's controller (instance id,
        or "kb"), or None (back). online: () -> (text, connected) for the partner's card."""
        ui = self.ui
        joined = [None] * slots   # each player's device
        ready = [False] * slots
        char = list(self.characters[:slots])
        names = {}
        while True:
            for a in ui.events(raw=True):
                if a == "quit":
                    raise SystemExit
                if not (isinstance(a, tuple) and a[0] == "event"):
                    continue
                ev = a[1]
                if ev.type == pygame.CONTROLLERBUTTONDOWN:
                    dev = ev.instance_id
                    key = {pygame.CONTROLLER_BUTTON_A: "ok", pygame.CONTROLLER_BUTTON_START: "ok",
                           pygame.CONTROLLER_BUTTON_B: "back", pygame.CONTROLLER_BUTTON_DPAD_LEFT: "left",
                           pygame.CONTROLLER_BUTTON_DPAD_RIGHT: "right",
                           pygame.CONTROLLER_BUTTON_Y: "shortcuts"}.get(ev.button, "any")
                elif ev.type == pygame.KEYDOWN and not ev.mod & pygame.KMOD_ALT:
                    dev = "kb"
                    key = {pygame.K_RETURN: "ok", pygame.K_SPACE: "ok", pygame.K_ESCAPE: "back", pygame.K_AC_BACK: "back",
                           pygame.K_LEFT: "left", pygame.K_RIGHT: "right", pygame.K_s: "shortcuts"}.get(ev.key)
                    if key is None:
                        continue
                elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 3 and joined.count(None) == slots:
                    return None  # right click: back
                else:
                    continue
                if dev != "kb" and dev not in names:
                    self.pads.refresh()
                    names[dev] = self.pads.name(dev)
                mine = [i for i, d in enumerate(joined) if d == dev]
                # A new device joins the first free slot. So does the keyboard again, once its
                # first player is ready (two people, one keyboard: KEYS has two layouts).
                if not mine or (dev == "kb" and key == "ok" and ready[mine[-1]] and None in joined):
                    if key == "back":
                        if joined.count(None) == slots:
                            return None
                    elif None in joined:
                        joined[joined.index(None)] = dev
                    continue
                i = mine[-1]
                if key == "ok":
                    if self.playable(char[i]):
                        ready[i] = True
                    elif char[i] == 2:  # Maria: her disc isn't added yet
                        self.game_files()
                elif key == "back":
                    if ready[i]:
                        ready[i] = False
                    else:
                        joined[i] = None
                elif key == "shortcuts" and not ready[i]:
                    self.set_shortcuts(i, not self.shortcuts(i))
                elif key in ("left", "right") and not ready[i]:
                    char[i] = (char[i] + (1 if key == "right" else -1)) % len(CHARACTERS)
            partner = online() if online else None
            if None not in joined and all(ready) and (partner is None or partner[1]):
                self.pads.assign = list(joined) + [None] * (2 - slots)
                self.characters[:slots] = char
                self.settings["characters"] = list(self.characters)
                return list(joined)
            ui.frame("Press a button on your controller to join", subtitle)
            n = slots + (1 if online else 0)
            w = 300
            x0 = (SIZE[0] - n * w - (n - 1) * 30) // 2
            for k in range(n):
                box = pygame.Rect(x0 + k * (w + 30), 180, w, 240)
                if k < slots:
                    self._card(box, "You" if online else f"Player {k + 1}", joined[k], ready[k], char[k], names,
                               self.shortcuts(k))
                else:
                    self._partner_card(box, *partner)
            ui.footer("Joined? Left / right: character. Triangle / Y / S: shortcuts. Cross / A / Enter: ready. Circle / B / Esc: leave."
                      if joined.count(None) < slots else "No controller? Press Enter to play with the keyboard.   Esc: back")
            ui.flip()
            pygame.time.wait(16)

    def _card(self, box, title, dev, ready, char, names, shortcuts=True):
        s, ui = self.screen, self.ui
        joined = dev is not None  # a controller's instance id can be 0
        pygame.draw.rect(s, (40, 16, 24) if joined else (24, 14, 20), box, border_radius=10)
        pygame.draw.rect(s, OK_GREEN if ready else (GOLD if joined else DIM), box, 2, border_radius=10)
        t = ui.big.render(title, True, GOLD if joined else DIM)
        s.blit(t, t.get_rect(midtop=(box.centerx, box.y + 14)))
        if not joined:
            for k, line in enumerate(("Press any button", "on a controller", "", "(or Enter: keyboard)")):
                t = ui.small.render(line, True, DIM)
                s.blit(t, t.get_rect(midtop=(box.centerx, box.y + 80 + k * 24)))
            return
        name = "Keyboard" if dev == "kb" else names.get(dev, "Controller")
        t = ui.small.render(name[:32], True, INK)
        s.blit(t, t.get_rect(midtop=(box.centerx, box.y + 56)))
        cname, playable = CHARACTERS[char], self.playable(char)
        t = ui.big.render(cname, True, INK if playable else DIM)
        r = t.get_rect(midtop=(box.centerx, box.y + 104))
        s.blit(t, r)
        if not ready:  # arrows: the character can be changed
            for sign, x in ((-1, r.left - 22), (1, r.right + 22)):
                cy = r.centery
                pygame.draw.polygon(s, DIM, [(x + sign * 7, cy), (x - sign * 5, cy - 8), (x - sign * 5, cy + 8)])
        if not playable:  # Maria without her disc
            for k, line in enumerate(("Needs your Dracula X", "Chronicles disc (PSP)", "Cross / A: add it")):
                t = ui.small.render(line, True, DIM)
                s.blit(t, t.get_rect(midtop=(box.centerx, box.y + 138 + k * 18)))
        if playable:
            if not shortcuts:
                line = "Shortcuts off (Triangle / Y)"
            elif char == 0:
                line = "Spells on the right stick"
            else:
                line = "L2 high jump · R2 blade dash"
            t = ui.small.render(line, True, INK if shortcuts else DIM)
            s.blit(t, t.get_rect(midtop=(box.centerx, box.y + 146)))
        if ready:
            t = ui.big.render("Ready!", True, OK_GREEN)
        elif playable:
            t = ui.small.render("Cross / A when ready", True, DIM)
        else:
            return
        s.blit(t, t.get_rect(midtop=(box.centerx, box.y + 188)))

    def _partner_card(self, box, text, connected):
        s, ui = self.screen, self.ui
        pygame.draw.rect(s, (24, 20, 30), box, border_radius=10)
        pygame.draw.rect(s, OK_GREEN if connected else DIM, box, 2, border_radius=10)
        t = ui.big.render("Your partner", True, GOLD)
        s.blit(t, t.get_rect(midtop=(box.centerx, box.y + 14)))
        for k, part in enumerate(text.split("\n")):
            big = k == 1 and not connected and "-" in part and len(part) <= 9  # the room code
            t = (ui.title if big else ui.small).render(part, True, GOLD if big else (OK_GREEN if connected and k == 0 else INK))
            s.blit(t, t.get_rect(midtop=(box.centerx, box.y + 64 + k * 30 + (8 if k > 1 and not connected else 0))))

    # --- home

    def storage_line(self):
        from archive import total_savestates_size
        return f"Savestates: {human(total_savestates_size())}   ·   {paths.data_dir()}"

    def home(self):
        pending = None
        while True:
            try:
                if pending:
                    act, pending = pending, None
                    self.go(act)
                    continue
                items = [("Solo", "Play a castle by yourself: any castle, any time", "solo"),
                         ("Couch co-op", "Two players on this PC, each with a controller", "couch"),
                         ("Online co-op", "Play with a friend on their own PC or phone", "online"),
                         ("Settings", "Layout, pixels, music, boss aggro, game files (Maria), controls", "settings"),
                         ("Quit", "", "quit")]
                if ANDROID:  # one game per device on Android (design/M9)
                    items = [i for i in items if i[2] != "couch"]
                choice = self.ui.menu("", [i[:2] for i in items], footer=self.storage_line(), hero=True)
                if choice is not None:
                    if items[choice][2] == "quit":
                        return
                    self.go(items[choice][2])
            except Navigate as n:
                pending = n.action

    def go(self, act):
        """Where a home choice or a menu-bar item leads."""
        if act in ("couch", "new", "continue"):
            self.couch(act)
        elif act == "solo":
            self.solo()
        elif act == "online":
            self.online_menu()
        elif act == "settings":
            self.settings_menu()
        elif act == "savestates":
            self.savestates()
        elif act == "debug_starts":
            self.debug_starts()
        elif act == "controllers":
            self.lobby()
        elif act == "quit":
            raise SystemExit

    def pick_castle(self, heading, subtitle):
        """The castle list (design/M11): New castle, then castles by last played. Returns
        (castle, fresh), or None (back)."""
        from archive import Castle
        while True:
            castles = Castle.all()[:7]
            # Android can't make them, only get them by joining; a first game goes straight to a new castle
            tests = Castle.tests() or (castles and not ANDROID)
            if not castles and not tests:  # nothing to pick from: a new one
                return self.new_castle()
            items = [("New castle", "A new game, in a castle of its own")] + [(c.name, c.summary()) for c in castles]
            if tests:
                items.append(("Test castles", "Outside each boss and before each story scene, with a typical player's progress"))
            k = self.ui.menu(heading, items, subtitle)
            if k is None:
                return None
            if 0 < k <= len(castles):
                return castles[k - 1], False
            picked = self.new_castle() if k == 0 else self.pick_test_castle()
            if picked:
                return picked

    def pick_test_castle(self):
        """A test castle (Tucker, 2026-10-28): a fresh copy of it, to play like any castle (solo, on
        the couch, or hosted: the joiner gets it too). Made with the debug starts, from this disc."""
        from archive import Castle
        tests = Castle.tests()
        if not tests:
            if not self.ui.confirm("Test castles", "One castle outside each boss and before each story scene of the\n"
                                   "first castle, made from your disc (a few minutes, once). Make them now?"):
                return None
            self.make_debug_starts()
            tests = Castle.tests()
            if not tests:
                return None
        k = self.ui.menu("Test castles", [(t.info["name"], t.info.get("about") or t.summary()) for t in tests],
                         "Each starts outside its boss or scene, until you save. You play a copy: these stay as they are.")
        return None if k is None else (tests[k].fresh_copy(), False)

    def new_castle(self):
        """A new castle, named here (Tucker, 2026-10-28). Left empty, it takes the name typed at
        SOTN's own name entry, at its first save (design/M11). Returns (castle, True), or None."""
        from archive import Castle
        name = self.ask_text("Name your castle", "Or leave it empty: it takes the name you type when the game starts.",
                             footer="Type a name  ·  Enter: start  ·  Esc: back", limit=24)
        if name is None:
            return None
        return Castle.new(name=name or None), True

    def couch(self, act="couch"):
        from archive import Castle
        if self.lobby(subtitle="Player 1 plays the left screen, player 2 the right one.") is None:
            return
        castles = Castle.all()
        if act == "new" or (act == "continue" and not castles):
            picked = self.new_castle()
        elif act == "continue":
            picked = (castles[0], False)
        else:
            picked = self.pick_castle("Couch co-op: which castle?", "Player 1 is slot 1 of the castle, player 2 slot 2.")
        if picked:
            self.play(*picked)

    def solo(self):
        """One game, no partner: 1× boss HP, full XP (the game's duo balancing waits for a
        partner it never hears from). The castle's slot 2 stays as it was."""
        picked = self.pick_castle("Solo: which castle?", "Any castle: yours, or one you joined.")
        if not picked or self.lobby(1, subtitle="Playing solo.") is None:
            return
        castle, fresh = picked
        castle.played_here()
        try:
            with self.online_session(None, castle, rank=0) as s:
                s.solo = True
                s.joint.on_write = castle.saved
                self.continue_castle(s, castle, fresh)
                self.run_view(s, castle)
        finally:
            castle.tidy()

    def continue_castle(self, s, castle, fresh):
        """Loads a castle's cards and joint save (unless it's new) into the game(s)."""
        if fresh:
            return
        self.load_cards(s, castle)
        if castle.joint_save.exists() and self.boot_to_title(s, f"Continuing {castle.name}"):
            self.apply_players(s)
            s.joint.start = castle.info.get("start")  # a test castle not saved yet: outside its boss
            s.joint.resume()

    # --- playing

    def session(self, starts, playthrough, bios=None):
        from session import Session
        self.apply_bios(bios)
        return Session(self.disc(), starts=starts, audio=True,
                       session_file=playthrough.joint_save if playthrough else None,
                       characters=tuple(self.characters), blob=self.blob())

    def apply_players(self, s):
        """Each game gets its player's character (online: this player's own), from its next load."""
        blob = self.blob()
        for i, g in enumerate(s.games):
            g.host("set_player", character=self.characters[i], options=self.options(i), blob=blob)

    def run_view(self, s, playthrough, goal="", pvp=None):
        from gameview import GameView
        self.apply_players(s)
        if len(s.games) == 1:  # a castle's slot 1 is this machine's player: card A (design/M11)
            cards = (playthrough.card("A"),) if playthrough else None
        else:
            cards = (playthrough.card("A"), playthrough.card("B")) if playthrough else None
        view = GameView(s, self.display, self.pads, self.audio, playthrough, goal,
                        self.settings.get("music", "auto"), self.settings.get("aggro", 50), cards,
                        profile=bool(os.environ.get("COOP_PROFILE")), launcher=self,
                        partner_vol=self.settings.get("partner_vol", 60),
                        pvp=bool(self.settings.get("pvp")) if pvp is None else pvp)
        result = view.run()
        if result == "quit":
            raise SystemExit
        if isinstance(result, tuple) and result[0] == "navigate":
            raise Navigate(result[1])

    def load_cards(self, s, playthrough):
        if len(s.games) == 1:
            card = playthrough.card("A")
            if card.exists():
                s.local.load_card(card.read_bytes())
            return
        for who, g in zip("AB", (s.a, s.b)):
            card = playthrough.card(who)
            if card.exists():
                g.load_card(card.read_bytes())

    def boot_to_title(self, s, heading):
        """Steps the game(s) (unseen) to the title screen, with a progress bar."""
        for k in range(120):
            if all(g.read("g_GameState") == 1 for g in s.games):
                return True
            s.step(60)
            if "quit" in self.ui.events():
                raise SystemExit
            self.ui.frame(heading, "Starting the game" if len(s.games) == 1 else "Starting both games")
            self.ui.bar(k, 60)
            self.ui.flip()
        return False

    def play(self, castle, fresh=False):
        castle.played_here()
        try:
            with self.session((None, None), castle) as s:
                s.joint.on_write = castle.saved
                self.continue_castle(s, castle, fresh)
                self.run_view(s, castle)
        finally:
            castle.tidy()

    # --- online co-op (design/M7, design/M7b-netcode.md)

    def _clip_put(self, text):
        try:
            pygame.scrap.put_text(str(text))
        except Exception:  # noqa: BLE001
            pass

    def _clip_code(self):
        """The room code, connect code or ip:port on the clipboard, or "": never the rest of
        what's there (Tucker, 2026-10-28: the Join box had filled with text from another app)."""
        from link.rendezvous import find_connect_code
        try:
            return find_connect_code(pygame.scrap.get_text() or "")
        except Exception:  # noqa: BLE001
            return ""

    def ask_code(self, heading, subtitle, initial=""):
        """Prompts for a room code or IP:port. Typing, Ctrl+V, or paste from a controller (□ / X)."""
        return self.ask_text(heading, subtitle, initial, paste=self._clip_code,
                             footer="Type the code, or Ctrl+V to paste (Square / X on a controller)"
                                    "  ·  Enter: join  ·  Esc: back")

    def ask_text(self, heading, subtitle, initial="", paste=None, footer="", limit=64):
        """A line of text: typed (the on-screen keyboard on a phone), or pasted when `paste` gives
        it (Ctrl+V; Square / X, or A in an empty box, on a controller). Returns it, or None (back)."""
        text = initial
        pygame.key.start_text_input()
        try:
            while True:
                for ev in pygame.event.get():
                    if self.display.handle(ev):
                        continue
                    if ev.type in (pygame.QUIT, pygame.WINDOWCLOSE):
                        raise SystemExit
                    if ev.type == MENU_EVENT and self.action(ev.action) is False:
                        raise Navigate(ev.action)
                    if ev.type == pygame.KEYDOWN:
                        if ev.key == pygame.K_RETURN:
                            return text.strip()
                        if ev.key in (pygame.K_ESCAPE, pygame.K_AC_BACK):
                            return None
                        if ev.key == pygame.K_BACKSPACE:
                            text = text[:-1]
                        elif ev.key == pygame.K_v and (ev.mod & pygame.KMOD_CTRL) and paste:
                            text = paste()[:limit] or text
                    elif ev.type == pygame.TEXTINPUT and len(text) < limit:
                        if not (pygame.key.get_mods() & pygame.KMOD_CTRL):
                            text += ev.text[:limit - len(text)]
                    elif ev.type == pygame.CONTROLLERBUTTONDOWN:
                        if ev.button == pygame.CONTROLLER_BUTTON_B:
                            return None
                        if ev.button == pygame.CONTROLLER_BUTTON_X and paste:
                            text = paste()[:limit] or text
                        elif ev.button in (pygame.CONTROLLER_BUTTON_A, pygame.CONTROLLER_BUTTON_START):
                            if not text and paste:
                                text = paste()[:limit]
                            else:
                                return text.strip()
                self.ui.frame(heading, subtitle)
                box = pygame.Rect(SIZE[0] // 2 - 260, 230, 520, 52)
                pygame.draw.rect(self.screen, (30, 18, 26), box, border_radius=6)
                pygame.draw.rect(self.screen, GOLD, box, 2, border_radius=6)
                shown = text + ("_" if pygame.time.get_ticks() // 400 % 2 else " ")
                t = self.ui.big.render(shown, True, INK)
                self.screen.blit(t, (box.x + 16, box.y + 10))
                self.ui.footer(footer)
                self.ui.flip()
                pygame.time.wait(16)
        finally:
            pygame.key.stop_text_input()

    def online_menu(self):
        while True:
            items = [("Host", "Pick a castle; you get a room code to give your partner"),
                     ("Join your partner", "Type their room code: you play their castle, and keep a copy"),
                     ("Back", "")]
            choice = self.ui.menu("Online co-op", items,
                                  "Each of you plays on your own PC or phone, with the same version of SOTN Co-op.")
            if choice is None or choice == 2:
                return
            if choice == 0:
                picked = self.pick_castle("Host: which castle?", "Your partner joins it, and keeps a copy.")
                if picked:
                    self.host_online(*picked)
            else:
                self.join_online()

    def online_session(self, start, playthrough, rank=0, peer=None):
        from link.connect import GAME_PORT
        from session import OnlineSession
        self.apply_bios()
        return OnlineSession(
            self.disc(), start=start, rank=rank, peer=peer, audio=True, joint=True,
            session_file=playthrough.joint_save if playthrough else None,
            patch_crc=self.patch_crc(), blob=self.blob(),
            # tests: a fixed port (Android emulators: design/M9); else the usual one, which the LAN
            # broadcast finds (link/connect.py), or any free one
            port=int(os.environ["COOP_PORT"]) if os.environ.get("COOP_PORT") else (GAME_PORT, 0),
            in_process=ANDROID,  # Android can't start worker processes
        )

    def partner_line(self, s, waiting):
        """For the lobby's partner card: (text, connected). Raises ConnectFailed."""
        st = s.local.host("handshake_tick")
        c = s.local.host("connect_status") or {}
        if st.get("mismatch"):
            raise ConnectFailed(st["mismatch"])
        if st.get("partner_hello") and c.get("state", "connected") == "connected":
            ping = f"ping {st['rtt_ms']} ms" if st.get("rtt_ms") is not None else "measuring the ping…"
            return f"Connected!\n{ping}", True
        if c.get("state") == "failed":
            raise ConnectFailed(c.get("reason") or "")
        if c.get("left_s") is not None:
            # which step it's on: says at once which side is stuck (Tucker's Thor test, 2026-10-23)
            step = {"starting": "Finding my address", "waiting": "Waiting for your partner's game",
                    "punching": "Found your partner: reaching them"}.get(c.get("state"), "Still looking")
            if c.get("relay_error") and c.get("state") == "waiting":  # say so now, not in five minutes
                step = "Can't reach the room-code server\nLooking on this Wi-Fi"
            waiting += f"\n{step}: {c['left_s'] // 60}:{c['left_s'] % 60:02d} left"
        return waiting, False

    def host_online(self, castle, fresh=False):
        castle.played_here()
        try:
            self._host_online(castle, fresh)
        finally:
            castle.tidy()

    def _host_online(self, playthrough, fresh):
        from link.rendezvous import make_room_code
        with self.online_session(None, playthrough, rank=0) as s:
            s.joint.on_write = playthrough.saved
            s.local.host("set_castle", playthrough.meta())  # the joiner keeps a copy (design/M11)
            pvp = bool(self.settings.get("pvp"))
            s.local.host("set_pvp", pvp)  # the host's setting covers the session (M15)
            room = make_room_code()
            self._clip_put(room)
            s.local.host("start_connect", room, "host", app=VERSION)
            self.room_info = f"Hosting room {room}, on UDP port {s.port}."
            try:
                pvp_line = "\nPvP is on." if pvp else ""
                if self.lobby(1, lambda: self.partner_line(s, f"Room code\n{room}\nIt's on your clipboard:\nsend it to them.{pvp_line}"),
                              f"Give your partner the room code {room}: it's on your clipboard.") is None:
                    return
            except ConnectFailed as e:
                self.ui.message("Couldn't reach your partner", str(e))
                return
            finally:
                self.room_info = ""
            self.continue_castle(s, playthrough, fresh)
            self.run_view(s, playthrough)

    def join_online(self):
        from archive import Castle
        from link.rendezvous import ConnectError, parse_connect_input
        code = ""
        while True:
            code = self.ask_code("Join your partner",
                                 "Type the room code your partner gives you (like BAT-7K2Q).",
                                 initial=code or self._clip_code())
            if code is None:
                return
            try:
                kind, target = parse_connect_input(code)
            except ConnectError as e:
                self.ui.message("Check that code", str(e))
                continue
            with self.online_session(None, None, rank=1) as s:
                if kind == "room":
                    s.local.host("start_connect", target, "join", app=VERSION)
                    waiting = f"Room\n{target}\nlooking for your partner…"
                else:
                    s.connect(target)
                    waiting = f"{target[0]}:{target[1]}\nconnecting…"
                try:
                    if self.lobby(1, lambda: self.partner_line(s, waiting), "Joining your partner's game.") is None:
                        continue
                except ConnectFailed as e:
                    self.ui.message("Couldn't reach your partner", str(e))
                    continue
                # The host's castle: this player's copy of it (design/M11)
                theirs = s.local.host("status").get("partner_hello") or {}
                meta = theirs.get("castle")
                pvp = bool(theirs.get("pvp"))  # the host's setting (M15)
                castle = Castle.receive(meta) if meta else Castle.new(received=True)
                s.joint.path = castle.joint_save
                s.joint.on_write = lambda blobs, c=castle: c.saved(blobs, theirs=True)
                self.load_cards(s, castle)
                try:
                    self.run_view(s, castle, goal="PvP is on (your partner's setting): your attacks hurt each other." if pvp else "",
                                  pvp=pvp)
                finally:
                    s.joint.on_write = None
                castle.tidy()
                return

    # --- the rest

    def savestates(self):
        from archive import Castle, load_pair
        ui = self.ui
        while True:
            pts = Castle.all()
            if not pts:
                ui.message("Savestates", "No castles yet.")
                return
            choice = ui.menu("Savestates", [(f"{p.name}  —  {human(p.savestates_size())}", f"{len(p.savestate_pairs())} moments")
                                            for p in pts],
                             "Made at moments worth going back to: a new area, a boss, quitting. Never deleted unless you ask.",
                             self.storage_line())
            if choice is None:
                return
            p = pts[choice]
            act = ui.menu(p.name, [("Go back to a moment", ""), ("Open the folder", str(p.states)),
                                   ("Delete this playthrough's savestates", "Your saves (memory cards) are kept")],
                          f"{len(p.savestate_pairs())} moments, {human(p.savestates_size())}")
            if act == 0:
                pairs = p.savestate_pairs()
                if not pairs:
                    ui.message(p.name, "No savestates yet.")
                    continue
                k = ui.menu("Go back to…", [(label, "") for label, _, _ in pairs[:9]])
                if k is None or (None in self.pads.assign and self.lobby() is None):
                    continue
                label, fa, fb = pairs[k]
                a, b = load_pair(fa, fb)
                with tempfile.TemporaryDirectory(prefix="coop-") as tmp:
                    (Path(tmp) / "A.state").write_bytes(a)
                    (Path(tmp) / "B.state").write_bytes(b)
                    bios = Castle.state_bios(fa, BUNDLED_BIOS.parent, self.settings.get("bios") or LEGACY_BIOS)
                    with self.session((str(Path(tmp) / "A.state"), str(Path(tmp) / "B.state")), p, bios) as s:
                        s.joint.on_write = p.saved
                        self.load_cards(s, p)
                        self.run_view(s, p)
            elif act == 1:
                paths.open_folder(p.states)
            elif act == 2:
                if ui.confirm("Delete savestates?",
                              f"{p.name}: {len(p.savestate_pairs())} moments, {human(p.savestates_size())}.\n"
                              "Your saves (memory cards and joint save) are kept. This can't be undone.",
                              yes="Delete them", no="Keep them"):
                    p.delete_savestates()

    def debug_starts(self):
        import debugstarts
        starts = debugstarts.load(self.starts_dir(), self.patch_crc())
        if not starts or not any(v.get("save") for v in starts.values()):
            ask = ("They haven't been made for this version yet (about a minute). Make them now?" if not starts else
                   "There are new ones: one before each story scene, and one outside each boss, with the\n"
                   "level and gear a player usually has by then. Make them now (about a minute)?")
            if self.ui.confirm("Debug starts", ask):
                self.make_debug_starts()
            starts = debugstarts.load(self.starts_dir(), self.patch_crc())
            if not starts:
                return
        while True:
            groups = [("Bosses", "Outside each boss of the first castle, with a typical player's progress", "boss"),
                      ("Scenes", "Before each story scene of the first castle, with the progress of that point", "scene"),
                      ("Places", "Spots along the route, with the gear from the start", None)]
            group = self.ui.menu("Debug starts", [g[:2] for g in groups],
                                 "Both games start here, with throwaway memory cards. F9 still saves a bug report.")
            if group is None:
                return
            kind = groups[group][2]
            names = [n for n in starts if (kind and starts[n].get(kind)) or
                     (not kind and not starts[n].get("boss") and not starts[n].get("scene"))]
            k = self.ui.menu(groups[group][0],
                             [(n.removeprefix("Boss: ").removeprefix("Scene: "), starts[n]["about"]) for n in names])
            if k is not None:
                break
        if None in self.pads.assign and self.lobby() is None:
            return
        file = str(self.starts_dir() / starts[names[k]]["file"])
        with self.session((file, file), None) as s:
            self.run_view(s, None, goal=f"Debug start: {names[k]} — {starts[names[k]]['about']}")

    def settings_menu(self):
        ui = self.ui
        sel = 0
        while True:
            st = self.settings
            items = [(f"Layout: {LAYOUT_NAMES[st.get('layout', 'auto')]}", "Couch: how the two games share the window"),
                     (f"Music: {st.get('music', 'auto')}", "Couch: which game plays the music (auto: the left one while it's in play)"),
                     (f"Boss aggro: {st.get('aggro', 50)}%", "A boss's chance to switch to the other player, every 3 s"),
                     (f"Partner's sounds: {st.get('partner_vol', 60)}%", "How loud your partner's attacks and steps are, in your game"),
                     (f"PvP: {'on' if st.get('pvp') else 'off'}", "Players' attacks hurt each other (online, the host's setting counts)"),
                     ("Game files", "Your Symphony of the Night disc, Dracula X Chronicles (adds Maria), the BIOS"),
                     ("Controls", "Each player's button shortcuts, and Alucard's spells on the right stick"),
                     ("Open the data folder", str(paths.data_dir()))]
            k = ui.menu("Settings", items, footer=self.storage_line(), sel=sel)
            if k is None:
                return
            sel = k
            if k == 0:
                order = list(LAYOUT_NAMES)
                st["layout"] = order[(order.index(st.get("layout", "auto")) + 1) % len(order)]
            elif k == 1:
                st["music"] = {"auto": "left", "left": "right", "right": "auto"}[st.get("music", "auto")]
            elif k == 2:
                st["aggro"] = (st.get("aggro", 50) + 10) % 110
            elif k == 3:
                st["partner_vol"] = {20: 40, 40: 60, 60: 80, 80: 100}.get(st.get("partner_vol", 60), 20)
            elif k == 4:
                st["pvp"] = not st.get("pvp")
            elif k == 5:
                self.game_files()
            elif k == 6:
                self.controls_menu()
            elif k == 7:
                paths.open_folder(paths.data_dir())
            save_settings(st)
            self.menubar.update(st)

    def choose_bios(self):
        ui = self.ui
        k = ui.menu("BIOS", [("Use OpenBIOS (included)", "An open-source BIOS; co-op is tested with it"),
                             ("Use my console's BIOS", "")],
                    "A PlayStation BIOS file, dumped from your own console:\n"
                    "USA \"SCPH-1001\", \"SCPH-5501\" or \"SCPH-7001\" (a 512 KB file, e.g. scph5501.bin).")
        if k == 0:
            self.settings["bios"] = None
        elif k == 1:
            path = pick_file("Your PlayStation BIOS", [("BIOS", "*.bin *.BIN"), ("All", "*.*")])
            if path:
                if path.stat().st_size != 512 * 1024:
                    ui.message("That's not a BIOS", f"{path.name} is {human(path.stat().st_size)}: a PlayStation BIOS is 512 KB.")
                    return
                self.settings["bios"] = str(path)
        save_settings(self.settings)


def main():
    logging.basicConfig(filename=paths.data_dir() / "launcher.log", level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    if ANDROID:  # and to logcat too, where android/device.py log reads it
        logging.getLogger().addHandler(logging.StreamHandler(sys.stderr))
    os.environ["COOP_WORKER_LOG"] = str(paths.data_dir() / "session.log")  # the game processes' log
    log.info("start %s", VERSION)
    app = None
    try:
        app = Launcher()
        app.wizard()
        app.home()
    except SystemExit:
        pass
    except Exception:
        log.exception("crash")
        raise
    finally:
        if app:
            app.display.remember()
            save_settings(app.settings)
        pygame.quit()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
