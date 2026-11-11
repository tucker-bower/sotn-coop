"""Which castle: Continue (the one played last), New castle, or Load castle (the list of them all).
Each castle shows its save's icon, the one the game's own file select would, moving as it does there."""

from ..theme import DIM, GOLD, INK, shorten, wrap
from ..widgets import ROW, move, scroll
from .home import castle_lines, started

HEAD, MENU, INFO, LIST = (8, 6, 464, 22), (8, 34, 168, 96), (182, 34, 290, 96), (8, 34, 464, 192)


def castle_menu(m, heading, latest, has_castles, note=""):
    """Returns "continue", "new", "load", or None (back). latest: the castle Continue loads, or None."""
    items = ([("continue", "Continue")] if latest is not None else []) + [("new", "New castle")]
    if has_castles:
        items.append(("load", "Load castle"))
    items.append((None, "Back"))
    hints = {"continue": "The castle you played last", "new": "A new game, in a castle of its own",
             "load": "Every castle you have, and the test castles", None: ""}
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
        m.window(INFO)
        x, y = INFO[0] + 10, INFO[1] + 10
        for k, line in enumerate(wrap(hints[key], (INFO[2] - 20) // 8)[:2]):
            t.text(s, line, x, y + k * 10, DIM)
        if key == "continue":
            icon = latest.icon()
            if icon is not None:
                t.icon(s, icon, x, y + 20, scale=3)
            name, where, played = castle_lines(latest)
            left = x + (58 if icon is not None else 0)
            t.text(s, shorten(name, 26), left, y + 22, INK)
            t.text(s, shorten(where, 26), left, y + 36, DIM)
            t.text(s, shorten(played, 26), left, y + 50, DIM)
        if note:
            t.text(s, shorten(note, 56), 12, 140, DIM)
        m.footer("{x} select   {o} back", "Enter: select   Esc: back")
        m.show()


def castle_list(m, heading, castles, extras=(), sel=0):
    """Every castle, most recent first, then extras ([(key, label, hint)]: the test castles, the
    boss rush). Returns ("castle", castle), ("rules", castle) (Square / X / right click on one),
    an extra's key, or None (back)."""
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
        m.footer("{x} play   {s} castle settings   {o} back", "Enter: play   S: castle settings   Esc: back")
        m.show()
