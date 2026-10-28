"""A native Windows menu bar on the launcher's window (design/M7b-polish.md part 3, option A).

File / Game / View / Controllers / Help, as in any Windows program. A click posts a pygame
event (MENU_EVENT, with .action) that the launcher handles like any other input, so every item
is also reachable without the mouse from the controller's pause menu.

How: the menu is made with user32 (CreateMenu, AppendMenuW, SetMenu) on SDL's window, and the
window procedure is wrapped (SetWindowLongPtrW) to catch WM_COMMAND before SDL sees it. Other
platforms get no menu bar (the pause menu has everything)."""

import ctypes
import sys

import pygame

MENU_EVENT = pygame.event.custom_type()

# (label, action) or (label, [submenu]) or None (a separator). Actions are strings; "layout:side"
# style ones are radio choices, shown checked by update().
MENUS = [
    ("&File", [("&New game", "new"), ("&Continue", "continue"), ("&Savestates…", "savestates"), None,
               ("Open the &data folder", "data_folder"), None, ("E&xit", "quit")]),
    ("&Game", [("&Pause\tEsc", "pause"), ("&Report a problem\tF9", "report"), None,
               ("Leave to the &menu", "leave")]),
    ("&View", [("Automatic", "layout:auto"), ("Side by side", "layout:side"), ("Stacked (vertical monitor)", "layout:stacked"),
               ("Player 1 only", "layout:p1"), ("Player 2 only", "layout:p2"),
               ("Player 2 in its own window", "layout:windows"), None,
               ("&Fullscreen\tF11", "fullscreen")]),
    ("&Controllers", [("&Who plays with which controller…", "controllers"), ("&Keyboard keys", "keys")]),
    ("&Help", [("&How to play", "help_play"), ("&Online troubleshooting", "help_online"), None,
               ("&Developer", [("&Debug starts…", "debug_starts"), ("Simulate a &network", [
                   ("Off", "netsim:off"), ("Across an ocean", "netsim:transatlantic"),
                   ("Bad Wi-Fi", "netsim:wifi"), ("Phone hotspot", "netsim:cellular")]),
                   ("Open the &log", "open_log")]), None,
               ("&About SOTN Co-op", "about")]),
]

WM_COMMAND = 0x0111
GWLP_WNDPROC = -4
MF_STRING, MF_POPUP, MF_SEPARATOR = 0x0, 0x10, 0x800
MF_CHECKED, MF_UNCHECKED, MF_BYCOMMAND = 0x8, 0x0, 0x0


class WinMenu:
    def __init__(self, title):
        self.ok = False
        self.actions = {}   # command id -> action
        self.ids = {}       # action -> command id
        if sys.platform != "win32":
            return
        try:
            self._install(title)
            self.ok = True
        except Exception:  # noqa: BLE001 - no menu bar; the pause menu still has everything
            import logging
            logging.getLogger("launcher").exception("menu bar")

    def _install(self, title):
        from ctypes import wintypes
        u = ctypes.windll.user32
        self.u = u
        LRESULT = ctypes.c_ssize_t
        self.WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)
        u.CallWindowProcW.restype = LRESULT
        u.CallWindowProcW.argtypes = [ctypes.c_void_p, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        u.SetWindowLongPtrW.restype = ctypes.c_void_p
        u.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        u.FindWindowW.restype = wintypes.HWND
        u.CreateMenu.restype = wintypes.HMENU
        u.CreatePopupMenu.restype = wintypes.HMENU
        u.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
        u.CheckMenuItem.argtypes = [wintypes.HMENU, wintypes.UINT, wintypes.UINT]
        u.SetMenu.argtypes = [wintypes.HWND, wintypes.HMENU]
        u.DrawMenuBar.argtypes = [wintypes.HWND]
        self.hwnd = u.FindWindowW(None, title)
        if not self.hwnd:
            raise OSError("launcher window not found")
        self.bar = u.CreateMenu()
        next_id = [1000]

        def build(menu, items):
            for item in items:
                if item is None:
                    u.AppendMenuW(menu, MF_SEPARATOR, 0, None)
                elif isinstance(item[1], list):
                    sub = u.CreatePopupMenu()
                    build(sub, item[1])
                    u.AppendMenuW(menu, MF_POPUP, sub, item[0])
                else:
                    next_id[0] += 1
                    self.actions[next_id[0]] = item[1]
                    self.ids[item[1]] = next_id[0]
                    u.AppendMenuW(menu, MF_STRING, next_id[0], item[0])

        build(self.bar, MENUS)
        u.SetMenu(self.hwnd, self.bar)
        u.DrawMenuBar(self.hwnd)

        def proc(hwnd, msg, wparam, lparam):
            if msg == WM_COMMAND and (wparam & 0xFFFF) in self.actions and not (wparam >> 16):
                pygame.event.post(pygame.event.Event(MENU_EVENT, action=self.actions[wparam & 0xFFFF]))
                return 0
            return u.CallWindowProcW(self._old, hwnd, msg, wparam, lparam)

        self._proc = self.WNDPROC(proc)  # kept alive: Windows calls it for the window's lifetime
        self._old = u.SetWindowLongPtrW(self.hwnd, GWLP_WNDPROC, ctypes.cast(self._proc, ctypes.c_void_p))

    def update(self, settings):
        """Ticks the current layout and network simulation."""
        if not self.ok:
            return
        want = {f"layout:{settings.get('layout', 'auto')}",
                f"netsim:{settings.get('netsim') or 'off'}"}
        for action, cid in self.ids.items():
            if ":" in action:
                self.u.CheckMenuItem(self.bar, cid, MF_BYCOMMAND | (MF_CHECKED if action in want else MF_UNCHECKED))

    def show(self, on):
        """Hidden in fullscreen."""
        if self.ok:
            self.u.SetMenu(self.hwnd, self.bar if on else None)
            self.u.DrawMenuBar(self.hwnd)

    def click(self, action):
        """Tests: the click Windows would send for this item (through the real window procedure)."""
        if self.ok:
            self.u.PostMessageW(self.hwnd, WM_COMMAND, self.ids[action], 0)
