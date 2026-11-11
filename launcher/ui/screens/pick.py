"""A small choice in the middle of the screen (Host or Join): a few rows, each with a line saying
what it is."""

from ..theme import DIM, GOLD, shorten
from ..widgets import ROW, move

BOX = (100, 60, 280, 140)


def pick(m, heading, items, about=""):
    """items: [(key, label, what it is)]. Returns a key, or None (back)."""
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
        m.begin(heading, about)
        m.window(BOX)
        x = BOX[0] + 10
        t.text(s, shorten(heading, 32), x, BOX[1] + 8, GOLD)
        m.rows((BOX[0] + 4, BOX[1] + 24, BOX[2] - 8, len(items) * ROW), [i[1] for i in items], sel)
        y = BOX[1] + 30 + len(items) * ROW
        t.paragraph(s, items[sel][2], x, y, 32, 3, DIM)
        if about:
            t.paragraph(s, about, x, BOX[1] + BOX[3] - 24, 32, 2, DIM)
        m.footer("{x} select   {o} back", "Enter: select   Esc: back")
        m.show()
