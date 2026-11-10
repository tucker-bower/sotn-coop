"""The main menu: the logo, the ways to play, and on the right what the selected one is, with the
castle Continue would load. Two links for the mouse only: our GitHub page and our Discord."""

from ..theme import DIM, GOLD, INK, shorten, wrap
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


def home(m, items, about, version, sel=0, note=""):
    """items: [(key, label, hint)]. about(key) -> {"lines": [...], "castle": Castle or None,
    "portrait": a picture's name or None}. Returns an item's key, a link's ("link", url), or None
    (back: nothing to go back to, so it only moves to Quit)."""
    t, s, hover = m.theme, m.s, None
    if m.sound:
        m.sound.music(True)
    while True:
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
        key, _, hint = items[sel]
        m.begin("Home")
        m.window(TITLE)
        t.picture(s, "logo", TITLE[0] + 10, TITLE[1] + 5)
        t.text(s, "Co-op", 146, 22, GOLD)
        for k, line in enumerate(wrap(hint, 39)[:3]):
            t.text(s, line, 146, 38 + k * 10, DIM)
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
