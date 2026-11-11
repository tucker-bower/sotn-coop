"""A newer version is out: what's new in it, that the player's things are safe, Update now or Later."""

from ..theme import DIM, GOLD, GREEN, INK, shorten, wrap

BOX = (40, 20, 400, 216)


def update_prompt(m, new, mine, notes):
    """Returns "update" or "later"."""
    t, s, sel = m.theme, m.s, 0
    buttons = (("update", "Update now"), ("later", "Later"))
    while True:
        for a in m.poll():
            if a in ("left", "right", "up", "down"):
                sel = 1 - sel
            elif a == "ok":
                return buttons[sel][0]
            elif a == "back":
                return "later"
            elif isinstance(a, tuple) and a[0] in ("hover", "click") and isinstance(a[1], int):
                sel = a[1]
                if a[0] == "click":
                    return buttons[sel][0]
        m.begin("Update available", f"Version {new} is available (you have {mine})")
        m.window(BOX)
        x, y = BOX[0] + 12, BOX[1] + 10
        t.text(s, f"Version {new} is available", x, y, GOLD)
        t.text(s, f"You have {mine}", x, y + 12, DIM)
        y += 32
        for line in notes[:8]:
            for k, part in enumerate(wrap(line, 45)[:2]):
                t.text(s, ("- " if k == 0 else "  ") + part, x, y, INK)
                y += 10
            if y > BOX[1] + 150:
                break
        y = BOX[1] + BOX[3] - 52
        for k, line in enumerate(wrap("Your castles, saves and discs are safe: they're in the data folder, and the "
                                      "update only replaces the program.", 46)[:2]):
            t.text(s, line, x, y + k * 10, GREEN)
        for k, (_, label) in enumerate(buttons):
            bx = x + k * 120
            if k == sel:
                t.cursor(s, (bx - 4, BOX[1] + BOX[3] - 24, 108, 14))
            t.text(s, shorten(label, 13), bx + 4, BOX[1] + BOX[3] - 21, INK)
            m.hit(k, (bx - 4, BOX[1] + BOX[3] - 26, 108, 18))
        m.footer("{x} select   {o} later", "Enter: select   Esc: later")
        m.show()
