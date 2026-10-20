"""The launcher's window: menus, the games, and how they're laid out (design/M7b-polish.md part 3).

Everything goes through SDL's GPU renderer, so a maximized or fullscreen window costs nothing
to fill:
- menus are drawn on a fixed-size canvas (CANVAS) and scaled to fit the window, letterboxed;
- each game is drawn at its true 4:3 shape (a PlayStation picture is 4:3 whatever its pixel
  width), never stretched (D76). "Sharp" scaling first enlarges it by whole pixels, then
  smooths only the last fraction ("sharp bilinear"), so pixels stay crisp and even at any
  window size; "Smooth" filters all the way;
- layouts: side by side, stacked (a vertical monitor), one player only, or player 2 in a
  window of its own (a second monitor or TV). Online, there's only your own game.
The window remembers its size; F11 or Alt+Enter toggles fullscreen."""

import os

import pygame
from pygame._sdl2.video import Renderer, Texture, Window

CANVAS = (1032, 532)
BAR = 26               # the status bar under the games (window pixels)
GAP = 8
LAYOUTS = ("auto", "side", "stacked", "p1", "p2", "windows")
LAYOUT_NAMES = {"auto": "Automatic", "side": "Side by side", "stacked": "Stacked (vertical monitor)", "p1": "Player 1 only",
                "p2": "Player 2 only", "windows": "Player 2 in its own window"}
SCALINGS = ("sharp", "smooth")
SCALING_NAMES = {"sharp": "Sharp", "smooth": "Smooth"}


def fit(area, aspect=4 / 3):
    """The largest aspect-shaped rect centered in area (x, y, w, h)."""
    x, y, w, h = area
    if w <= 0 or h <= 0:
        return pygame.Rect(x, y, 0, 0)
    if w / h > aspect:
        nw, nh = round(h * aspect), h
    else:
        nw, nh = w, round(w / aspect)
    return pygame.Rect(x + (w - nw) // 2, y + (h - nh) // 2, nw, nh)


def cells(layout, size, players):
    """Where each game goes in the main window: [rect or None per game]."""
    w, h = size
    h -= BAR
    if layout == "auto":  # whichever gives each game the bigger picture
        side = min((w - GAP) / 2 * 3 / 4, h)
        stacked = min(w * 3 / 4, (h - GAP) / 2)
        layout = "side" if side >= stacked else "stacked"
    if players == 1:
        return [fit((0, 0, w, h))]
    if layout == "stacked":
        half = (h - GAP) // 2
        return [fit((0, 0, w, half)), fit((0, half + GAP, w, half))]
    if layout == "p1":
        return [fit((0, 0, w, h)), None]
    if layout in ("p2", "windows"):
        return [None, fit((0, 0, w, h))] if layout == "p2" else [fit((0, 0, w, h)), None]
    half = (w - GAP) // 2
    return [fit((0, 0, half, h)), fit((half + GAP, 0, half, h))]


def texture(renderer, size, linear, **kw):
    """A texture that scales nearest-neighbour or linearly (SDL decides when it's created)."""
    old = os.environ.get("SDL_RENDER_SCALE_QUALITY")
    os.environ["SDL_RENDER_SCALE_QUALITY"] = "1" if linear else "0"
    try:
        return Texture(renderer, size, **kw)
    finally:
        if old is None:
            del os.environ["SDL_RENDER_SCALE_QUALITY"]
        else:
            os.environ["SDL_RENDER_SCALE_QUALITY"] = old


class GameTexture:
    """One game's picture on the GPU: the frame as it came, and its whole-pixel enlargement."""

    def __init__(self, renderer):
        self.r = renderer
        self.src = None
        self.big = None
        self.size = None
        self.mode = None
        self._last = None

    def update(self, surface, scaling="sharp"):
        if (self.src is None or self.size != surface.get_size() or self.mode != scaling):
            self.src = texture(self.r, surface.get_size(), scaling == "smooth", streaming=True)
            self.big = None
            self.mode = scaling
        self.src.update(surface)
        self.size = surface.get_size()
        self._last = surface

    def draw(self, rect, scaling):
        if self.src is None or not rect or rect.w <= 0:
            return
        if scaling != self.mode and self._last is not None:
            self.update(self._last, scaling)
        if scaling == "smooth":
            self.src.draw(dstrect=rect)
            return
        # Sharp: enlarge by whole pixels (nearest) to at least the target size, then smooth the
        # rest of the way down. Width and height scale separately (PlayStation pixels aren't square).
        sw, sh = self.size
        kx, ky = max(1, -(-rect.w // sw)), max(1, -(-rect.h // sh))
        want = (sw * kx, sh * ky)
        if self.big is None or (self.big.width, self.big.height) != want:
            self.big = texture(self.r, want, True, target=True)
        self.r.target = self.big
        self.src.draw(dstrect=(0, 0, *want))
        self.r.target = None
        self.big.draw(dstrect=rect)


class Display:
    def __init__(self, settings, title="SOTN Co-op"):
        self.settings = settings
        settings["_fullscreen"] = False
        w, h = settings.get("window_size") or (CANVAS[0], CANVAS[1] + 60)
        pygame.display.init()
        self.window = Window(title, size=(max(640, w), max(360, h)), resizable=True)
        icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")
        self.icon = pygame.image.load(icon) if os.path.exists(icon) else None
        if self.icon:
            self.window.set_icon(self.icon)
        if settings.get("window_pos"):
            try:
                self.window.position = tuple(settings["window_pos"])
            except Exception:  # noqa: BLE001 - that monitor is gone
                pass
        if settings.get("window_maximized"):
            self.window.maximize()
        self.window.minimum_size = (640, 360)
        self.renderer = Renderer(self.window, accelerated=-1, vsync=False)
        self.canvas = pygame.Surface(CANVAS, pygame.SRCALPHA)
        self._canvas_tex = None
        self.games = []
        self.second = None   # (Window, Renderer, GameTexture) for the "windows" layout
        self._bar_tex = None
        self._bar_key = None
        self.font = pygame.font.SysFont("consolas", 15)
        self.on_resize = []
        self.on_fullscreen = []  # f(fullscreen): the menu bar hides in fullscreen
        self._last = ("canvas", False)  # what the window shows: the canvas (over the games?), or the games

    # --- settings

    @property
    def layout(self):
        return self.settings.get("layout", "auto")

    @property
    def scaling(self):
        s = self.settings.get("scaling", "sharp")
        return s if s in SCALINGS else "sharp"

    def remember(self):
        try:
            self.settings["window_pos"] = list(self.window.position)
            if not self.settings.get("window_maximized") and not self.fullscreen:
                self.settings["window_size"] = list(self.window.size)
        except Exception:  # noqa: BLE001
            pass

    @property
    def fullscreen(self):
        return bool(self.settings.get("_fullscreen"))

    def toggle_fullscreen(self):
        if self.fullscreen:
            self.window.set_windowed()
            self.settings["_fullscreen"] = False
        else:
            self.remember()
            self.window.set_fullscreen(desktop=True)
            self.settings["_fullscreen"] = True
        for f in self.on_fullscreen:
            f(self.fullscreen)

    def handle(self, ev):
        """Window events the display looks after itself. True if it used the event."""
        if ev.type == pygame.KEYDOWN and (ev.key == pygame.K_F11 or
                                          (ev.key == pygame.K_RETURN and ev.mod & pygame.KMOD_ALT)):
            self.toggle_fullscreen()
            return True
        if ev.type == pygame.WINDOWMAXIMIZED:
            self.settings["window_maximized"] = True
        elif ev.type == pygame.WINDOWRESTORED:
            self.settings["window_maximized"] = False
        elif ev.type in (pygame.WINDOWRESIZED, pygame.WINDOWSIZECHANGED, pygame.WINDOWMOVED):
            self.remember()
            for f in self.on_resize:
                f()
        elif ev.type == pygame.WINDOWCLOSE and self.second and getattr(ev, "window", None) is self.second[0]:
            self.settings["layout"] = "auto"  # closing player 2's window brings it back
            self.close_second()
            return True
        return False

    # --- menus

    def canvas_rect(self):
        return fit((0, 0, *self.window.size), CANVAS[0] / CANVAS[1])

    def to_canvas(self, pos):
        """A window position (the mouse) in canvas coordinates, or None outside it."""
        r = self.canvas_rect()
        if not r.collidepoint(pos) or r.w == 0:
            return None
        return ((pos[0] - r.x) * CANVAS[0] // r.w, (pos[1] - r.y) * CANVAS[1] // r.h)

    def present(self, over_games=False):
        """Shows the canvas (a menu). over_games: on top of the last game pictures, dimmed."""
        self._last = ("canvas", over_games)
        self._render()
        self.renderer.present()

    def _render(self):
        r = self.renderer
        kind, arg = self._last
        if kind == "games":
            r.draw_color = (0, 0, 0, 255)
            r.clear()
            self._draw_games()
            self._draw_bar(*arg)
            return
        r.draw_color = (12, 8, 14, 255)
        r.clear()
        if arg:
            self._draw_games()
        if self._canvas_tex is None:
            self._canvas_tex = texture(r, CANVAS, True, streaming=True)
            self._canvas_tex.blend_mode = pygame.BLENDMODE_BLEND
        self._canvas_tex.update(self.canvas)
        self._canvas_tex.draw(dstrect=self.canvas_rect())

    # --- games

    def ensure_games(self, n):
        while len(self.games) < n:
            self.games.append(GameTexture(self.renderer))
        if n == 2 and self.layout == "windows" and not self.second:
            win = Window("SOTN Co-op: player 2", size=(800, 600), resizable=True)
            if self.icon:
                win.set_icon(self.icon)
            ren = Renderer(win, accelerated=-1, vsync=False)
            self.second = (win, ren, GameTexture(ren))
        elif self.second and (n != 2 or self.layout != "windows"):
            self.close_second()

    def close_second(self):
        if self.second:
            self.second[0].destroy()
            self.second = None

    def _draw_games(self):
        rects = cells(self.layout, self.window.size, len(self.games))
        for g, rect in zip(self.games, rects):
            g.draw(rect, self.scaling)

    def present_games(self, frames, status=(), color=(230, 230, 230)):
        """frames: a Surface (or None: keep the last one) per game. status: lines for the bar."""
        self.ensure_games(len(frames))
        for i, f in enumerate(frames):
            if f is not None:
                target = self.second[2] if (self.second and i == 1) else self.games[i]
                target.update(f, self.scaling)
                if self.second and i == 1:
                    self.games[1].size = target.size
        self._last = ("games", (status, color))
        self._render()
        self.renderer.present()
        if self.second:
            win, ren, tex = self.second
            ren.draw_color = (0, 0, 0, 255)
            ren.clear()
            tex.draw(fit((0, 0, *win.size)), self.scaling)
            ren.present()

    def _draw_bar(self, lines, color):
        w, h = self.window.size
        key = (tuple(lines), color, w)
        if key != self._bar_key:
            surf = pygame.Surface((w, BAR))
            surf.fill((16, 16, 24))
            x = 8
            for line in lines[-1:]:
                t = self.font.render(line, True, color)
                surf.blit(t, (x, (BAR - t.get_height()) // 2))
            self._bar_tex = Texture.from_surface(self.renderer, surf)
            self._bar_key = key
        self._bar_tex.draw(dstrect=(0, h - BAR, w, BAR))

    def screenshot(self):
        """The window as the player sees it (bug reports, tests): drawn again and read back,
        since what's on screen can't be read once it's been presented."""
        try:
            self._render()
            return self.renderer.to_surface()
        except Exception:  # noqa: BLE001
            return self.canvas.copy()
