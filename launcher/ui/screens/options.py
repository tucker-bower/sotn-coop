"""Options: everything in the window's menu bar and more, in one list a controller can reach
(the menu bar isn't there in fullscreen, on Android, or for a controller). Each row is a choice
(left / right, or OK, cycles it), a slider, a switch, or an action (OK opens it). The app builds
the rows (Launcher.option_rows) and does what they say."""

import pygame

from ..theme import DIM, GOLD, GREEN, INK, shorten, wrap
from ..widgets import ROW, scroll

HEAD, LIST, HINT = (8, 6, 464, 22), (8, 34, 464, 164), (8, 202, 464, 36)
BAR_X, BAR_W = 300, 100


def options(m, rows, change, sel=0, title="Options", note="Also in the menus at the top of the window", footer=None,
            status=None):
    """rows() -> [{"kind": "head" | "choice" | "slider" | "switch" | "action", "key", "label", "hint",
    "value", ("low", "high", "step" for a slider)}]. change(key, step) applies a choice, slider or
    switch (step -1 / +1, or 0 for OK). Returns (an action's key, the row it was on), ("drop", a
    file dropped on the window), ("more", key) (Square / X / S on a row), or None (back). The same
    screen lists other things than options: title and note say what. status() -> what just
    happened, shown above the selected row's explanation."""
    t, s, first = m.theme, m.s, 0
    table = rows()

    def step_sel(k, by):
        for _ in range(len(table)):
            k = (k + by) % len(table)
            if table[k]["kind"] != "head":
                return k
        return k

    if table[sel]["kind"] == "head":
        sel = step_sel(sel, 1)
    while True:
        for a in m.poll(raw=True):
            if isinstance(a, tuple) and a[0] == "event":
                if a[1].type == pygame.DROPFILE:
                    return "drop", a[1].file
                continue
            if a == "back":
                return None
            row = table[sel]
            if a == "rules" and row["kind"] == "action":
                return "more", row["key"]
            if a in ("up", "down"):
                sel = step_sel(sel, -1 if a == "up" else 1)
            elif a in ("left", "right") and row["kind"] in ("choice", "slider", "switch"):
                change(row["key"], -1 if a == "left" else 1)
            elif a == "ok" or (isinstance(a, tuple) and a[0] == "click" and isinstance(a[1], int)):
                if isinstance(a, tuple):
                    sel = a[1]
                    row = table[sel]
                if row["kind"] == "action":
                    return row["key"], sel
                if row["kind"] in ("choice", "switch"):
                    change(row["key"], 0)
            elif isinstance(a, tuple) and a[0] == "click" and isinstance(a[1], tuple):  # a slider's bar
                k = a[1][1]
                row, sel = table[k], k
                at = m.ui.display.to_pixels(pygame.mouse.get_pos()) if hasattr(m.ui.display, "to_pixels") else None
                share = max(0.0, min(1.0, ((at[0] if at else BAR_X) - BAR_X) / BAR_W))
                target = row["low"] + round(share * (row["high"] - row["low"]) / row["step"]) * row["step"]
                change(row["key"], (target - row["value"]) // row["step"])
            elif isinstance(a, tuple) and a[0] == "hover" and isinstance(a[1], int) and table[a[1]]["kind"] != "head":
                sel = a[1]
        table = rows()
        sel = min(sel, len(table) - 1)
        fits = (LIST[3] - 12) // ROW
        first = scroll(first, sel, fits, len(table))
        if first and table[first - 1]["kind"] == "head" and sel - first < fits - 1:
            first -= 1
        said = status() if status else ""
        m.begin(title, said or table[sel].get("hint", ""))
        m.window(HEAD)
        t.text(s, title, HEAD[0] + 8, HEAD[1] + 7, GOLD)
        t.text_right(s, note[:56 - len(title) - 2], HEAD[0] + HEAD[2] - 8, HEAD[1] + 7, DIM)
        m.window(LIST)
        x, y0, w = LIST[0] + 4, LIST[1] + 6, LIST[2] - 8
        right = LIST[0] + LIST[2] - 12
        for k in range(first, min(len(table), first + fits)):
            row, y = table[k], y0 + (k - first) * ROW
            if row["kind"] == "head":
                t.text(s, row["label"], x + 6, y + 3, GOLD)
                continue
            if k == sel:
                t.cursor(s, (x, y, w, ROW - 2))
            kind = row["kind"]
            room = {"switch": 48 + 8, "slider": right - BAR_X + 8}.get(kind, 0)
            if kind in ("choice", "action") and row.get("value"):
                room = (len(str(row["value"])) + (4 if kind == "choice" and k == sel else 0)) * 8 + 8
            t.text(s, shorten(row["label"], max(4, (right - x - 14 - room) // 8)), x + 14, y + 3, INK)
            if kind == "switch":
                t.switch(s, row["value"], LIST[0] + LIST[2] - 60, y - 1)
            elif kind == "choice":
                arrows = k == sel
                t.text_right(s, ("{<} " if arrows else "") + str(row["value"]) + (" {>}" if arrows else ""), right, y + 3, INK)
            elif kind == "slider":
                bar = pygame.Rect(BAR_X, y + 4, BAR_W, 6)
                pygame.draw.rect(s, (16, 16, 48), bar)
                pygame.draw.rect(s, GOLD if k == sel else DIM, (bar.x, bar.y, bar.w * (row["value"] - row["low"]) // (row["high"] - row["low"]), bar.h))
                pygame.draw.rect(s, INK, bar, 1)
                t.text_right(s, f"{row['value']}%", right, y + 3, INK)
                m.hit(("bar", k), bar.inflate(8, 10))
            elif kind == "action" and row.get("value"):
                t.text_right(s, str(row["value"]), right, y + 3, row.get("colour", GREEN))
            m.hit(k, (x, y, (BAR_X - x - 8) if kind == "slider" else w, ROW))
        if first:
            t.text(s, "{^}", LIST[0] + LIST[2] - 14, LIST[1] + 2)
        if first + fits < len(table):
            t.text(s, "{v}", LIST[0] + LIST[2] - 14, LIST[1] + LIST[3] - 10)
        m.window(HINT)
        lines = [(line, INK) for line in wrap(said, 56)[:2]] if said else []
        lines += [(line, DIM) for line in wrap(table[sel].get("hint", ""), 56)][:3 - len(lines)]
        for k, (line, colour) in enumerate(lines):
            t.text(s, line, HINT[0] + 8, HINT[1] + 6 + k * 10, colour)
        m.footer(*(footer or ("{<}{>} change   {x} select   {o} back", "Left / right: change   Enter: select   Esc: back")))
        m.show()
