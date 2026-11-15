"""Which castle: Continue (the one played last), New castle, Load castle (the list of them all), or
Test castles.
Each castle shows its save's icon, the one the game's own file select would, moving as it does there."""

from ..theme import DIM, GLYPH, GOLD, INK, shorten, width
from ..widgets import ROW, move, scroll
from .home import castle_lines, started

HEAD, MENU, INFO, LIST = (8, 6, 464, 22), (8, 34, 168, 96), (182, 34, 290, 96), (8, 34, 464, 192)


def castle_menu(m, heading, latest, has_castles, has_tests=False):
    """Returns "continue", "new", "load", "tests", or None (back). latest: the castle Continue loads,
    or None. Nothing but the choices, and what Continue loads (Tucker, 2026-11-11)."""
    items = ([("continue", "Continue")] if latest is not None else []) + [("new", "New castle")]
    if has_castles:
        items.append(("load", "Load castle"))
    if has_tests:
        items.append(("tests", "Test castles"))
    items.append((None, "Back"))
    t, s, sel = m.theme, m.s, 0
    while True:
        for a in m.poll():
            if a in ("up", "down"):
                sel = move(sel, a, len(items))
            elif a == "ok":
                return items[sel][0]
            elif a == "back":
                return None
            elif isinstance(a, tuple) and a[0] in ("hover", "click") and isinstance(a[1], int):
                sel = a[1]
                if a[0] == "click":
                    return items[sel][0]
        key = items[sel][0]
        m.begin(heading)
        m.window(HEAD)
        t.text(s, heading, HEAD[0] + 8, HEAD[1] + 7, GOLD)
        m.window(MENU)
        m.rows((MENU[0] + 4, MENU[1] + 10, MENU[2] - 8, len(items) * ROW), [i[1] for i in items], sel)
        if key == "continue":  # what it loads
            m.window(INFO)
            x, y = INFO[0] + 10, INFO[1] + 10
            icon = latest.icon()
            if icon is not None:
                t.icon(s, icon, x, y + 10, scale=3)
            name, where, played = castle_lines(latest)
            left = x + (58 if icon is not None else 0)
            t.text(s, shorten(name, 26), left, y + 12, INK)
            t.text(s, shorten(where, 26), left, y + 26, DIM)
            t.text(s, shorten(played, 26), left, y + 40, DIM)
        m.footer("{x} select   {o} back", "Enter: select   Esc: back")
        m.show()


def castle_list(m, heading, castles, extras=(), sel=0):
    """Every castle, most recent first, then extras ([(key, label, hint)]: the test castles, the
    boss rush). Returns ("castle", castle), ("rules", castle) (Square / X / right click on one),
    ("history", castle) (Triangle / Y / H, or a click on the footer's "save history": #278), an
    extra's key, or None (back)."""
    t, s, first = m.theme, m.s, 0
    count = len(castles) + len(extras)
    inside = (LIST[0] + 4, LIST[1] + 8, LIST[2] - 8, LIST[3] - 16)
    while True:
        for a in m.poll():
            if a in ("up", "down"):
                sel = move(sel, a, count)
            elif a == "ok" or (isinstance(a, tuple) and a[0] == "click" and isinstance(a[1], int)):
                if isinstance(a, tuple):
                    sel = a[1]
                return ("castle", castles[sel]) if sel < len(castles) else extras[sel - len(castles)][0]
            elif a == "back":
                return None
            elif a == "rules" and sel < len(castles):
                return ("rules", castles[sel])
            elif (a == "history" or a == ("click", "history")) and sel < len(castles):
                return ("history", castles[sel])
            elif isinstance(a, tuple) and a[0] == "hover" and isinstance(a[1], int):
                sel = a[1]
        first = scroll(first, sel, inside[3] // ROW, count)
        m.begin(heading)
        m.window(HEAD)
        t.text(s, heading, HEAD[0] + 8, HEAD[1] + 7, GOLD)
        m.window(LIST)

        def draw(row, x, y, selected):
            if isinstance(row, tuple):  # an extra
                t.text(s, row[1], x + 22, y, GOLD)
                return
            icon = row.icon()
            if icon is not None:
                t.icon(s, icon, x, y - 3, moving=selected)  # (16 high in a 14-high bar: as the file select's)
            name, where, _ = castle_lines(row)
            t.text(s, shorten(name, 20), x + 22, y, INK)
            t.text(s, started(row), x + 190, y, INK if selected else DIM)
            t.text(s, shorten(where, 25), x + 246, y, INK if selected else DIM)

        m.rows(inside, list(castles) + list(extras), sel, first, draw=draw)
        if sel < len(castles):
            line = castle_lines(castles[sel])[2] + ("   " + castles[sel].rules_line() if castles[sel].rules_line() else "")
        else:
            line = extras[sel - len(castles)][2]
        t.text(s, shorten(line, 58), 8, 230, DIM)
        m.footer("{x} play   {s} castle settings   {t} save history   {o} back",
                 "Enter: play   S: settings   H: save history   Esc: back")
        if sel < len(castles):  # the mouse's way to it: the footer's words
            words = "{t} save history" if m.device == "pad" else "H: save history"
            footer = "{x} play   {s} castle settings   " if m.device == "pad" else "Enter: play   S: settings   "
            m.hit("history", (8 + width(footer) - 2, 241, width(words) + 4, GLYPH + 5))
        m.show()


def moment_label(label):
    """A savestate's file label ("20261114-203412 New area Castle Keep") as a row: its date and
    time, then what happened."""
    import time
    stamp, _, what = label.partition(" ")
    try:
        stamp = time.strftime("%b %d, %H:%M", time.strptime(stamp, "%Y%m%d-%H%M%S"))  # as the castle list's "Played"
    except ValueError:
        pass
    return f"{stamp}  {what}"


def save_history(m, name, labels, sel=0):
    """A castle's moments, newest first (#278). Returns the chosen index, or None (back)."""
    t, s, first = m.theme, m.s, 0
    inside = (LIST[0] + 4, LIST[1] + 8, LIST[2] - 8, LIST[3] - 16)
    rows = [moment_label(label) for label in labels]
    while True:
        for a in m.poll():
            if a in ("up", "down"):
                sel = move(sel, a, len(rows))
            elif a == "ok" or (isinstance(a, tuple) and a[0] == "click" and isinstance(a[1], int)):
                return a[1] if isinstance(a, tuple) else sel
            elif a == "back":
                return None
            elif isinstance(a, tuple) and a[0] == "hover" and isinstance(a[1], int):
                sel = a[1]
        first = scroll(first, sel, inside[3] // ROW, len(rows))
        m.begin("Save history", name)
        m.window(HEAD)
        t.text(s, "Save history", HEAD[0] + 8, HEAD[1] + 7, GOLD)
        t.text_right(s, shorten(name, 36), HEAD[0] + HEAD[2] - 8, HEAD[1] + 7, INK)
        m.window(LIST)
        m.rows(inside, rows, sel, first)
        t.text(s, "Play from a moment, then save at a coffin to keep it.", 8, 230, DIM)
        m.footer("{x} play from here   {o} back", "Enter: play from here   Esc: back")
        m.show()
