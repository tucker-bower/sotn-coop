"""Your discs: Symphony of the Night for the PlayStation, which everything is made from, and the
two that unlock more characters. Drop a file anywhere on the window, or select a slot to browse:
a file goes to its own slot by what's in it. On first run nothing but Quit leaves this screen
until the PlayStation disc is attached."""

import pygame

from ..theme import DIM, GOLD, GREEN, INK, RED, shorten, wrap

HEAD, NOTE = (8, 6, 464, 34), (8, 182, 464, 36)
SLOT_Y, SLOT_W, SLOT_H = 46, 150, 132
SLOTS = (  # (key, title, system, needed?, what it's for: three lines of 17 at most)
    ("ps1", ("Symphony of", "the Night"), "PlayStation (USA)", "Required", "Co-op is made from it."),
    ("psp", ("Dracula X", "Chronicles"), "PSP (USA)", "Optional", "Unlocks Co-op and Ultimate Maria."),
    ("saturn", ("Symphony of", "the Night"), "Saturn (Japan)", "Optional", "Unlocks Saturn Maria, Ultimate Richter."),
)


def discs(m, status, attach, first_run=False, said="", more=()):
    """status() -> {slot: the attached file's name, or None}. attach(slot, path) attaches a disc
    (path None: the player browses for that slot's; slot None: a dropped file, sorted by what's in
    it) and returns (slot it went to or None, what to say, went well?). Returns "continue" (first
    run, with the PlayStation disc there), "back", "quit", or one of more (buttons after Back)."""
    t, s = m.theme, m.s
    have = status()
    said = {"slot": None, "text": said, "ok": True}
    buttons = ["Continue", "Quit"] if first_run else ["Back", *more]
    row, col = (1, 0) if have.get("ps1") and first_run else (0, 0)  # row 0: the slots; row 1: the buttons

    def do(slot, path):
        nonlocal have, row, col
        where, text, ok = attach(slot, path)
        said.update(slot=where, text=text, ok=ok)
        have = status()
        if first_run and have.get("ps1") and ok:
            row, col = 1, 0  # ready: Continue

    while True:
        for a in m.poll(raw=True):
            if isinstance(a, tuple) and a[0] == "event":
                if a[1].type == pygame.DROPFILE:
                    do(None, a[1].file)
                continue
            if a in ("left", "right") :
                col = (col + (1 if a == "right" else -1)) % (3 if row == 0 else len(buttons))
            elif a in ("up", "down"):
                row, col = 1 - row, 0
                if row == 0:
                    col = 0
            elif a == "back" and not first_run:
                return "back"
            elif a == "ok" or (isinstance(a, tuple) and a[0] == "click" and a[1] is not None):
                if isinstance(a, tuple):
                    row, col = a[1]
                if row == 0:
                    do(SLOTS[col][0], None)
                    continue
                pick = buttons[col]
                if pick == "Continue":
                    if have.get("ps1"):
                        return "continue"
                    said.update(slot="ps1", text="Attach your PlayStation Symphony of the Night disc first.", ok=False)
                else:
                    return pick if pick in more else pick.lower()
            elif isinstance(a, tuple) and a[0] == "hover" and a[1] is not None:
                row, col = a[1]
        m.begin("Discs", said["text"])
        m.window(HEAD)
        t.text(s, "Your discs", HEAD[0] + 8, HEAD[1] + 7, GOLD)
        t.text(s, "PlayStation: needed. PSP and Saturn: more characters.", HEAD[0] + 8, HEAD[1] + 19, DIM)
        for k, (key, title, system, need, unlocks) in enumerate(SLOTS):
            x = 8 + k * (SLOT_W + 7)
            box = (x, SLOT_Y, SLOT_W, SLOT_H)
            m.window(box)
            on = row == 0 and col == k
            if on:
                t.cursor(s, (x + 3, SLOT_Y + 3, SLOT_W - 6, 26))
            y = SLOT_Y + 6
            for line in title:
                t.text(s, line, x + 8, y, INK)
                y += 10
            y += 6
            t.text(s, system, x + 8, y, DIM)
            t.text(s, need, x + 8, y + 12, GOLD if need == "Required" else DIM)
            y += 28
            for line in wrap(unlocks, 17)[:3]:
                t.text(s, line, x + 8, y, DIM)
                y += 10
            y = SLOT_Y + 96
            if have.get(key):
                t.text(s, "Attached", x + 8, y, GREEN)
                t.text(s, shorten(have[key], 16), x + 8, y + 12, DIM)
            else:
                t.text(s, "Drop it here, or", x + 8, y, INK if on else DIM)
                t.text(s, "select to browse", x + 8, y + 10, INK if on else DIM)
            if said["slot"] == key and not said["ok"]:
                t.text(s, "Didn't work", x + 8, y + 24, RED)
            m.hit((0, k), box)
        m.window(NOTE)
        lines = wrap(said["text"] or "Drop your disc images anywhere on this window.", 56)
        if len(lines) > 3:
            lines = lines[:2] + [shorten(" ".join(lines[2:]), 56)]
        for k, line in enumerate(lines):
            t.text(s, line, NOTE[0] + 8, NOTE[1] + 6 + k * 10, INK if said["ok"] else RED)
        for k, label in enumerate(buttons):
            x = 8 + k * 100
            on = row == 1 and col == k
            if on:
                t.cursor(s, (x, 224, 92, 14))
            ready = label != "Continue" or have.get("ps1")
            t.text(s, label, x + 6, 227, INK if ready else DIM)
            m.hit((1, k), (x, 222, 92, 18))
        m.footer("{x} select   {<}{>} move", "Enter: select   Arrows: move" + ("" if first_run else "   Esc: back"))
        m.show()
