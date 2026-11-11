"""The main menu: the logo, the ways to play, and on the right what the selected one is, with the
castle Continue would load. Two links for the mouse only: our GitHub page and our Discord."""

import pygame

from ..theme import DIM, INK, shorten, wrap
from ..widgets import ROW, move

LINKS = {"github": "https://github.com/tucker-bower/sotn-coop", "discord": "https://discord.gg/q7V9eFtAW"}
TITLE, MENU, INFO = (8, 6, 464, 74), (8, 86, 160, 146), (174, 86, 298, 146)


def castle_lines(castle):
    """A castle in three short lines: its name, where and what level, when it was started and last played."""
    import time
    info = castle.info
    name = (info.get("name") or "New castle") + (f" ({info['copy']})" if info.get("copy") else "")
    where = "  ".join(b for b in (info.get("where"), f"Lv {info['level']}" if info.get("level") else None) if b)
    day = "%b %d, %H:%M"
    when = time.strftime(f"Played {day}", time.localtime(info.get("played", info.get("created", 0))))
    return name, where or "Not saved yet", when


def started(castle):
    """ "Nov 08": the day a castle began (what tells two of the same name apart)."""
    import time
    return time.strftime("%b %d", time.localtime(castle.info.get("created", 0)))


LEFT, RIGHT = ("alucard", "richter", "richter-saturn"), ("maria", "maria-saturn")
FACES_LEFT = {"alucard"}  # (his frame is the Doppelganger's, facing left; the others face right)


def title_art(t, s):
    lw, lh = t.pictures["logo"].get_size()
    scrawl = t.pictures.get("scrawl")
    sh = scrawl.get_height() if scrawl else 0
    lx, ly = TITLE[0] + (TITLE[2] - lw) // 2, TITLE[1] + (TITLE[3] - lh - sh) // 2
    t.picture(s, "logo", lx, ly)
    if scrawl:
        s.blit(scrawl, (lx + (lw - scrawl.get_width()) // 2, ly + lh - 2))
    floor = TITLE[1] + TITLE[3] - 3
    x = lx - 10  # leftwards from the logo, each facing it
    for name in LEFT:
        p = t.pictures.get("sprite-" + name)
        if p and x - p.get_width() > TITLE[0] + 2:
            x -= p.get_width()
            s.blit(pygame.transform.flip(p, True, False) if name in FACES_LEFT else p, (x, floor - p.get_height()))
            x -= 10
    x = lx + lw + 10
    for name in RIGHT:
        p = t.pictures.get("sprite-" + name)
        if p and x + p.get_width() < TITLE[0] + TITLE[2] - 2:
            s.blit(p if name in FACES_LEFT else pygame.transform.flip(p, True, False), (x, floor - p.get_height()))
            x += p.get_width() + 10


def home(m, items, about, version, sel=0, note="", interrupt=None):
    """items: [(key, label, hint)]. about(key) -> {"lines": [...], "castle": Castle or None,
    "portrait": a picture's name or None}. Returns an item's key, a link's ("link", url), or None
    (back: nothing to go back to, so it only moves to Quit). interrupt() -> a key to return at once
    (an update found while the menu was up), or None."""
    t, s, hover, frames = m.theme, m.s, None, 0
    while True:
        if m.sound and frames % 30 == 0:  # (again now and then: the first time, it's still being decoded)
            m.sound.music(True)
        frames += 1
        if interrupt and interrupt():
            return interrupt()
        for a in m.poll():
            if a in ("up", "down"):
                sel = move(sel, a, len(items))
            elif a == "ok":
                return items[sel][0]
            elif a == "back":
                sel = len(items) - 1
            elif isinstance(a, tuple) and a[0] in ("hover", "click"):
                hover = a[1] if isinstance(a[1], str) else None
                if isinstance(a[1], int):
                    sel = a[1]
                    if a[0] == "click":
                        return items[sel][0]
                elif a[0] == "click" and a[1] in LINKS:
                    return ("link", LINKS[a[1]])
        key = items[sel][0]
        m.begin("Home")
        m.window(TITLE)  # the logo, Tucker's "co-op" under it, and the characters the player has (issue 232)
        title_art(t, s)
        m.window(MENU)
        m.rows((MENU[0] + 4, MENU[1] + 10, MENU[2] - 8, len(items) * ROW), [i[1] for i in items], sel)
        m.window(INFO)
        what = about(key) or {}
        x, y = INFO[0] + 10, INFO[1] + 10
        castle, portrait = what.get("castle"), what.get("portrait")
        room = 34 - (9 if portrait else 0)  # characters across, beside the portrait
        for line in what.get("lines", ()):
            for part in wrap(line, room):
                t.text(s, part, x, y, DIM)
                y += 10
            y += 2
        if castle is not None:
            icon = castle.icon()
            if icon is not None:
                t.icon(s, icon, x, y + 4, scale=2)
            name, where, played = castle_lines(castle)
            left = x + (40 if icon is not None else 0)
            t.text(s, shorten(name, room - 5), left, y + 4, INK)
            t.text(s, shorten(where, room - 5), left, y + 16, DIM)
            t.text(s, shorten(played, room - 5), left, y + 28, DIM)
        if portrait:
            pw, ph = t.pictures[portrait].get_size()
            t.picture(s, portrait, INFO[0] + INFO[2] - pw - 10, INFO[1] + (INFO[3] - ph) // 2)
        m.footer("{x} select", "Enter: select   Arrows: move", f"{note}   v{version}" if note else f"v{version}")
        m.link("github", "GitHub", 8, 258, hover)
        m.link("discord", "Join our Discord and meet people to play with!", 472, 258, hover, right=True)
        m.show()
