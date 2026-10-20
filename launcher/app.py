"""SOTN Co-op: the player's launcher (design/M6-playable-build.md).

    python launcher/app.py

First run: a short wizard (your disc image, then each player's controller, then the debug
starts). After that: one big button, Continue or New game. Everything else is one level down:
savestates, debug starts, settings. Menus work with a controller (d-pad, cross/A = OK,
circle/B = back) or the keyboard (arrows, Enter, Esc).
"""

import logging
import multiprocessing
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
for sub in ("launcher", "harness", "patcher", ""):
    sys.path.insert(0, str(APP / sub) if sub else str(APP))

import pygame  # noqa: E402

import paths  # noqa: E402
from paths import human, load_settings, save_settings  # noqa: E402

TITLE = "Castlevania: Symphony of the Night  —  Co-op"
SIZE = (1032, 532)
INK, DIM, GOLD, BLOOD, BG = (230, 225, 215), (150, 145, 140), (240, 205, 120), (150, 20, 30), (12, 8, 14)
BUNDLED_BIOS = APP / "bios" / "openbios.bin"
PATCH = APP / "patcher" / "sotn-coop.bps"

log = logging.getLogger("launcher")


class UI:
    """Drawing and input for the menus."""

    def __init__(self, screen):
        self.screen = screen
        self.title = pygame.font.SysFont("georgia", 34, bold=True)
        self.big = pygame.font.SysFont("georgia", 26)
        self.small = pygame.font.SysFont("georgia", 17)
        self.mono = pygame.font.SysFont("consolas", 14)

    def events(self):
        """Menu actions this frame: "up", "down", "left", "right", "ok", "back", "quit", or ("pad", id)."""
        out = []
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                out.append("quit")
            elif ev.type == pygame.KEYDOWN:
                a = {pygame.K_UP: "up", pygame.K_DOWN: "down", pygame.K_LEFT: "left", pygame.K_RIGHT: "right",
                     pygame.K_RETURN: "ok", pygame.K_SPACE: "ok", pygame.K_ESCAPE: "back"}.get(ev.key)
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
            elif ev.type == pygame.CONTROLLERDEVICEADDED:
                pygame._sdl2.controller.Controller(ev.device_index)
        return out

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
            for k, line in enumerate(subtitle.split("\n")):
                t = self.small.render(line, True, DIM)
                s.blit(t, ((SIZE[0] - t.get_width()) // 2, 128 + k * 22))

    def items(self, items, sel, top=200, hero=False):
        """hero: the first item is the big button (home: Continue / New game)."""
        y = top
        for k, (label, hint) in enumerate(items):
            color = GOLD if k == sel else INK
            if hero and k == 0:
                t = self.title.render(label, True, color)
                box = pygame.Rect(0, 0, max(t.get_width() + 60, 420), t.get_height() + 24)
                box.center = (SIZE[0] // 2, y + box.height // 2)
                pygame.draw.rect(self.screen, (60, 10, 18) if k == sel else (30, 14, 20), box, border_radius=8)
                pygame.draw.rect(self.screen, GOLD if k == sel else DIM, box, 2, border_radius=8)
                self.screen.blit(t, t.get_rect(center=box.center))
                y += box.height + 22
                if k == sel and hint:
                    h = self.small.render(hint, True, DIM)
                    self.screen.blit(h, ((SIZE[0] - h.get_width()) // 2, SIZE[1] - 64))
                continue
            t = self.big.render(("›  " if k == sel else "   ") + label, True, color)
            self.screen.blit(t, (SIZE[0] // 2 - 140, y))
            y += 38
            if k == sel and hint:
                h = self.small.render(hint, True, DIM)
                self.screen.blit(h, ((SIZE[0] - h.get_width()) // 2, SIZE[1] - 64))

    def footer(self, text):
        t = self.mono.render(text, True, DIM)
        self.screen.blit(t, ((SIZE[0] - t.get_width()) // 2, SIZE[1] - 30))

    def bar(self, done, total, y=300):
        w = SIZE[0] - 300
        pygame.draw.rect(self.screen, DIM, (150, y, w, 18), 1)
        pygame.draw.rect(self.screen, BLOOD, (152, y + 2, int((w - 4) * done / max(total, 1)), 14))

    def menu(self, heading, items, subtitle="", footer="", hero=False):
        """Returns the chosen index, or None (back)."""
        sel = 0
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
            self.frame(heading, subtitle)
            self.items(items, sel, top=(130 if hero else 200) + 22 * subtitle.count("\n"), hero=hero)
            if footer:
                self.footer(footer)
            pygame.display.flip()
            pygame.time.wait(16)

    def message(self, heading, text, button="OK"):
        self.menu(heading, [(button, "")], text)

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
            pygame.display.flip()
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


def pick_file(title, types):
    """The system's file picker: Windows' own dialog, or tkinter elsewhere."""
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
        pygame.display.set_caption("SOTN Co-op")
        self.screen = pygame.display.set_mode(SIZE)
        self.ui = UI(self.screen)
        from gameview import Pads
        self.settings = load_settings()
        self.pads = Pads(self.settings.get("pads") or (None, None))
        self.audio = None
        try:
            from gameview import Audio
            self.audio = Audio()
        except Exception:  # noqa: BLE001 - no sound device: play silent
            log.exception("audio")

    # --- the environment the games run in

    def bios(self):
        b = self.settings.get("bios")
        return Path(b) if b and Path(b).exists() else BUNDLED_BIOS

    def apply_bios(self):
        os.environ["COOP_BIOS"] = str(self.bios())

    def disc(self):
        d = self.settings.get("disc")
        return Path(d) if d and Path(d).exists() else None

    def starts_dir(self):
        return paths.debug_starts_dir() / f"{self.disc().stem}@{self.bios().stem}"

    # --- first run

    def wizard(self):
        ui = self.ui
        while not self.disc():
            choice = ui.menu("Welcome", [("Choose my disc image", "Your own Symphony of the Night (USA) rip: the .cue file"),
                                         ("Quit", "")],
                             "Co-op is made from your own copy of the game: a disc image of\n"
                             "Castlevania: Symphony of the Night, USA version (SLUS-00067), as .cue + .bin.\n"
                             "Your file is never changed: the co-op disc is made next to it.")
            if choice != 0:
                raise SystemExit
            path = pick_file("Your Symphony of the Night disc image (.cue)", [("Disc image", "*.cue *.bin"), ("All", "*.*")])
            if not path:
                continue
            import patcher
            try:
                cue = ui.wait_for("Making the co-op disc", f"From {path.name}\nThis takes a few seconds.",
                                  lambda progress: patcher.apply(path, PATCH, progress=progress))
            except (patcher.DiscError, patcher.bps.PatchError) as e:
                ui.message("That disc won't work", str(e))
                continue
            self.settings["disc"] = str(cue)
            save_settings(self.settings)
            ui.message("Co-op disc ready", f"Made {cue.name}\nnext to your disc image.")
        if not self.settings.get("pads_set"):
            self.assign_pads()
        if not (self.starts_dir() / "index.json").exists():
            self.make_debug_starts()

    def assign_pads(self):
        ui = self.ui
        assign = [None, None]
        for player in range(2):
            got = None
            while got is None:
                acts = ui.events()
                if "quit" in acts:
                    raise SystemExit
                pressed = [a[1] for a in acts if isinstance(a, tuple) and a[0] == "pad" and a[1] not in assign]
                if pressed:
                    got = pressed[0]
                elif "ok" in acts:  # Enter on the keyboard (a pad's button came with a "pad" above)
                    got = "keyboard"
                ui.frame(f"Player {player + 1}: press a button on your controller",
                         ("Player 1 plays the left screen, player 2 the right one.\n"
                          "No controller? Press Enter to use the keyboard for this player."))
                pygame.display.flip()
                pygame.time.wait(16)
            assign[player] = None if got == "keyboard" else got
            pygame.time.wait(300)
            pygame.event.clear()
        self.settings["pads"] = assign
        self.settings["pads_set"] = True
        save_settings(self.settings)
        self.pads.assign = list(assign)

    def make_debug_starts(self):
        import debugstarts
        self.apply_bios()
        proc, queue = debugstarts.start(self.disc(), self.starts_dir())
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
                    return
            if "quit" in self.ui.events():
                proc.terminate()
                raise SystemExit
            self.ui.frame("Making the debug starts",
                          "Savestates to start anywhere on the route, for testing and bug reports.\n"
                          f"Made from your disc, once. {text}...")
            self.ui.bar(done, total)
            pygame.display.flip()
            pygame.time.wait(30)

    # --- home

    def storage_line(self):
        from archive import total_savestates_size
        return f"Savestates: {human(total_savestates_size())}   ·   {paths.data_dir()}"

    def home(self):
        from archive import Playthrough
        while True:
            pts = Playthrough.all()
            items, actions = [], []
            if pts:
                items.append((f"Continue: {pts[0].name}", "Both games load your last joint save"))
                actions.append(("continue", pts[0]))
            items.append(("New game", "Both players start a new game (each picks a name)"))
            actions.append(("new", None))
            for label, hint, act in (("Savestates", "Go back to a moment of a playthrough; see the space they use", "states"),
                                     ("Debug starts", "Start both games anywhere on the route (testing)", "debug"),
                                     ("Settings", "Controllers, music, boss aggro, BIOS, folders", "settings"),
                                     ("Quit", "", "quit")):
                items.append((label, hint))
                actions.append((act, None))
            choice = self.ui.menu("", items, footer=self.storage_line(), hero=True)
            if choice is None:
                continue
            act, arg = actions[choice]
            if act == "quit":
                return
            if act == "new":
                self.play(Playthrough.new(), fresh=True)
            elif act == "continue":
                self.play(arg)
            elif act == "states":
                self.savestates()
            elif act == "debug":
                self.debug_starts()
            elif act == "settings":
                self.settings_menu()

    # --- playing

    def session(self, starts, playthrough):
        from session import Session
        self.apply_bios()
        return Session(self.disc(), starts=starts, audio=True,
                       session_file=playthrough.joint_save if playthrough else None)

    def run_view(self, s, playthrough, goal=""):
        from gameview import GameView
        cards = (playthrough.card("A"), playthrough.card("B")) if playthrough else None
        view = GameView(s, self.screen, self.pads, self.audio, playthrough, goal,
                        self.settings.get("music", "auto"), self.settings.get("aggro", 50), cards)
        if view.run() == "quit":
            raise SystemExit

    def load_cards(self, s, playthrough):
        for who, g in zip("AB", (s.a, s.b)):
            card = playthrough.card(who)
            if card.exists():
                g.load_card(card.read_bytes())

    def boot_to_title(self, s, heading):
        """Steps both games (unseen) to the title screen, with a progress bar."""
        for k in range(120):
            if all(g.read("g_GameState") == 1 for g in (s.a, s.b)):
                return True
            s.step(60)
            if "quit" in self.ui.events():
                raise SystemExit
            self.ui.frame(heading, "Starting both games")
            self.ui.bar(k, 60)
            pygame.display.flip()
        return False

    def play(self, playthrough, fresh=False):
        with self.session((None, None), playthrough) as s:
            if not fresh:
                self.load_cards(s, playthrough)
            if not fresh and playthrough.joint_save.exists() and self.boot_to_title(s, f"Continuing {playthrough.name}"):
                s.joint.resume()
            playthrough.save_info()
            self.run_view(s, playthrough)

    def savestates(self):
        from archive import Playthrough, load_pair
        ui = self.ui
        while True:
            pts = Playthrough.all()
            if not pts:
                ui.message("Savestates", "No playthroughs yet.")
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
                if k is None:
                    continue
                label, fa, fb = pairs[k]
                a, b = load_pair(fa, fb)
                with tempfile.TemporaryDirectory(prefix="coop-") as tmp:
                    (Path(tmp) / "A.state").write_bytes(a)
                    (Path(tmp) / "B.state").write_bytes(b)
                    with self.session((str(Path(tmp) / "A.state"), str(Path(tmp) / "B.state")), p) as s:
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
        starts = debugstarts.load(self.starts_dir())
        if not starts:
            if self.ui.confirm("Debug starts", "They haven't been made yet (about a minute). Make them now?"):
                self.make_debug_starts()
            starts = debugstarts.load(self.starts_dir())
            if not starts:
                return
        names = list(starts)
        k = self.ui.menu("Debug starts", [(n, starts[n]["about"]) for n in names],
                         "Both games start here, with throwaway memory cards. F9 still saves a bug report.")
        if k is None:
            return
        file = str(self.starts_dir() / starts[names[k]]["file"])
        with self.session((file, file), None) as s:
            self.run_view(s, None, goal=f"Debug start: {names[k]} — {starts[names[k]]['about']}")

    def settings_menu(self):
        ui = self.ui
        while True:
            st = self.settings
            bios = "OpenBIOS (included)" if self.bios() == BUNDLED_BIOS else f"Your BIOS: {self.bios().name}"
            items = [(f"Music: {st.get('music', 'auto')}", "Which game plays the music (auto: the left one while it's in play)"),
                     (f"Boss aggro: {st.get('aggro', 50)}%", "A boss's chance to switch to the other player, every 3 s"),
                     ("Controllers: assign again", "Press a button on each player's controller"),
                     (bios, "Change the BIOS"),
                     ("Disc: choose again", self.settings.get("disc") or ""),
                     ("Open the data folder", str(paths.data_dir()))]
            k = ui.menu("Settings", items, footer=self.storage_line())
            if k is None:
                return
            if k == 0:
                st["music"] = {"auto": "left", "left": "right", "right": "auto"}[st.get("music", "auto")]
            elif k == 1:
                st["aggro"] = (st.get("aggro", 50) + 10) % 110
            elif k == 2:
                self.assign_pads()
            elif k == 3:
                self.choose_bios()
            elif k == 4:
                st["disc"] = None
                save_settings(st)
                self.wizard()
            elif k == 5:
                paths.open_folder(paths.data_dir())
            save_settings(st)

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
    log.info("start")
    app = Launcher()
    try:
        app.wizard()
        app.home()
    except SystemExit:
        pass
    except Exception:
        log.exception("crash")
        raise
    finally:
        pygame.quit()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
