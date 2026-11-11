"""A castle's settings (launcher/rules.py): the mode of a new castle, the difficulty, then every
rule under its group's heading. Sliders are bars (left / right, or a click on the bar), rules are
the game's own ON / OFF switches (OK, or a click). Each change is applied at once."""

import pygame

import rules as castle_rules

from ..theme import DIM, GOLD, GREEN, INK, shorten, wrap
from ..widgets import ROW, scroll

HEAD, LIST, HINT = (8, 6, 464, 22), (8, 34, 464, 148), (8, 186, 464, 52)
BAR_X, BAR_W = 300, 100          # a slider's bar
MODES = (("story", "Story", "The game from its start."),
         ("rush", "Boss rush", "All 22 bosses back to back, each with a typical player's progress, timed."))
DIFFICULTY_HINT = ("Sets enemy HP, damage taken and XP together. Easy: 100% HP with a partner, half damage, more XP. "
                   "Medium: 200% HP. Hard: 300%, more damage, half XP. Nightmare: 400%, double damage.")


def table(rules, start, mode, read_only):
    """The screen's rows: (kind, key). Headings aren't selectable."""
    out = [("start", "")] if start else []
    if mode is not None and "mode" in mode:
        out.append(("mode", ""))
    if mode is not None and "presets" in mode:
        out.append(("preset", ""))
    out.append(("difficulty", ""))
    sliders = {s[0] for s in castle_rules.SLIDERS}
    for heading, keys in castle_rules.GROUPS:
        out.append(("head", heading))
        out += [("slider" if k in sliders else "toggle", k) for k in keys]
    if rules["remap"]:
        out += [("button", b) for b in castle_rules.REMAP_BUTTONS]
    if not read_only:
        out.append(("defaults", ""))
    return out


def castle_settings(m, name, rules, apply, read_only=False, start=False, mode=None):
    """Shows and changes rules (a dict, changed in place; apply(rules) after each change). start: a
    new castle, with a Start row first. mode: {"mode": "story" or "rush"} for a new castle that can
    be a boss rush (changed in place), or a castle's mode as text to show. Returns "start", or None
    (back)."""
    t, s = m.theme, m.s
    sliders = {x[0]: x for x in castle_rules.SLIDERS}
    toggles = {x[0]: x for x in castle_rules.TOGGLES}
    choose_mode = isinstance(mode, dict)
    rows = table(rules, start, mode if choose_mode else None, read_only)
    sel, first = 0, 0

    def change(row, step):
        """step: -1 / +1 (left / right), 0 (OK or a click)."""
        kind, key = row
        if kind == "mode":
            if choose_mode:
                mode["mode"] = "rush" if mode["mode"] == "story" else "story"
            return
        if kind == "preset":
            ids = [p for p, _ in mode["presets"]]
            mode["preset"] = ids[(ids.index(mode.get("preset")) + (step or 1)) % len(ids)]
            return
        if read_only:
            return
        if kind == "difficulty":
            castle_rules.set_difficulty(rules, castle_rules.next_difficulty(rules, step or 1))
        elif kind == "slider" and step:
            low, high, each = sliders[key][4:]
            rules[key] = max(low, min(high, rules[key] + step * each))
        elif kind == "toggle":
            rules[key] = not rules[key] if step == 0 else step > 0
        elif kind == "button":
            castle_rules.set_target(rules, key, castle_rules.next_target(rules, key))
        elif kind == "defaults" and step == 0:
            rules.clear()
            rules.update(castle_rules.clean({}))
        else:
            return
        apply(dict(rules))

    def step_sel(sel, by):
        while True:
            sel = (sel + by) % len(rows)
            if rows[sel][0] != "head":
                return sel

    while True:
        for a in m.poll():
            if a == "back":
                return None
            if a in ("up", "down"):
                sel = step_sel(sel, -1 if a == "up" else 1)
            elif a in ("left", "right"):
                change(rows[sel], -1 if a == "left" else 1)
            elif a == "ok":
                if rows[sel][0] == "start":
                    return "start"
                change(rows[sel], 0)
            elif isinstance(a, tuple) and a[0] in ("hover", "click") and a[1] is not None:
                bar = isinstance(a[1], tuple) and a[1][0] == "bar"
                k = a[1][1] if bar else a[1]
                if not isinstance(k, int) or k >= len(rows) or rows[k][0] == "head":
                    continue
                sel = k
                if a[0] == "click":
                    if rows[k][0] == "start":
                        return "start"
                    if bar and not read_only:  # where on the bar it was clicked
                        low, high, each = sliders[rows[k][1]][4:]
                        try:
                            at = m.ui.display.to_pixels(pygame.mouse.get_pos())
                        except AttributeError:
                            at = None
                        share = ((at[0] if at else BAR_X) - BAR_X) / BAR_W
                        rules[rows[k][1]] = low + round(max(0, min(1, share)) * (high - low) / each) * each
                        apply(dict(rules))
                    elif rows[k][0] != "slider":
                        change(rows[k], 0)
        rows = table(rules, start, mode if choose_mode else None, read_only)
        sel = min(sel, len(rows) - 1)
        if rows[sel][0] == "head":
            sel = step_sel(sel, 1)
        fits = (LIST[3] - 12) // ROW
        first = scroll(first, sel, fits, len(rows))
        if first and rows[first - 1][0] == "head" and sel - first < fits - 1:
            first -= 1  # keep a group's heading above its first rule

        m.begin("Castle settings")
        m.window(HEAD)
        t.text(s, "Castle settings", HEAD[0] + 8, HEAD[1] + 7, GOLD)
        t.text_right(s, shorten(name, (HEAD[2] - 16) // 8 - len("Castle settings") - 3), HEAD[0] + HEAD[2] - 8, HEAD[1] + 7, DIM)
        m.window(LIST)
        hint = ""
        x, y0, w = LIST[0] + 4, LIST[1] + 6, LIST[2] - 8
        for k in range(first, min(len(rows), first + fits)):
            kind, key = rows[k]
            y = y0 + (k - first) * ROW
            on = k == sel
            if on:
                t.cursor(s, (x, y, w, ROW - 2))
            ty, value, label, plain = y + 3, None, "", True
            if kind == "head":
                t.text(s, key, x + 6, ty, GOLD)
                continue
            if kind == "start":
                label, row_hint = "Start", "Play with these settings."
            elif kind == "mode":
                current = next(mo for mo in MODES if mo[0] == mode["mode"])
                label, value, row_hint = "Mode", current[1], current[2]
            elif kind == "preset":
                label, value, row_hint = "Mod preset", dict(mode["presets"]).get(mode.get("preset"), "?"), \
                    "The castle's mods, made in Mods on the main menu. Co-op (no mods) is the original game."
            elif kind == "difficulty":
                now = castle_rules.difficulty(rules)
                label, value, row_hint, plain = "Difficulty", now, DIFFICULTY_HINT, now == "Medium"
            elif kind == "slider":
                _, label, row_hint, default, low, high, _ = sliders[key]
                plain = rules[key] == default
                bar = pygame.Rect(BAR_X, y + 4, BAR_W, 6)
                pygame.draw.rect(s, (16, 16, 48), bar)
                pygame.draw.rect(s, GOLD if on else DIM, (bar.x, bar.y, bar.w * (rules[key] - low) // (high - low), bar.h))
                pygame.draw.rect(s, INK, bar, 1)
                t.text_right(s, f"{rules[key]}%", LIST[0] + LIST[2] - 12, ty, INK if plain else GREEN)
                m.hit(("bar", k), bar.inflate(8, 10))
            elif kind == "toggle":
                _, label, row_hint, default = toggles[key][:4]
                plain = rules[key] == default
                t.switch(s, rules[key], LIST[0] + LIST[2] - 60, y - 1)
                if not plain:
                    t.text_right(s, "changed", LIST[0] + LIST[2] - 68, ty, GREEN)
            elif kind == "button":
                names = castle_rules.BUTTON_NAMES
                label, value, row_hint = f"{names[key]} acts as", names[rules["remap_map"].get(key, key)], "For both players."
            else:
                label, row_hint = "Back to the defaults", "Every setting as it comes."
            t.text(s, label, x + (6 if kind in ("start", "mode", "preset", "difficulty", "defaults") else 14), ty, INK)
            if value is not None:
                arrows = kind in ("mode", "preset", "difficulty") and on and not (read_only and kind == "difficulty")
                room = (LIST[2] - 32 - len(label) * 8) // 8 - (8 if arrows else 0)  # (what's left of the row after its label)
                t.text_right(s, ("{<} " if arrows else "") + shorten(str(value), room) + (" {>}" if arrows else ""), LIST[0] + LIST[2] - 12, ty, INK if plain else GREEN)
            if on:
                hint = row_hint
            if not (kind == "slider"):
                m.hit(k, (x, y, w, ROW))
            else:
                m.hit(k, (x, y, BAR_X - x - 8, ROW))
        if first:
            t.text(s, "{^}", LIST[0] + LIST[2] - 14, LIST[1] + 2)
        if first + fits < len(rows):
            t.text(s, "{v}", LIST[0] + LIST[2] - 14, LIST[1] + LIST[3] - 10)
        m.window(HINT)
        if read_only:  # (said first in the explanation window)
            hint = "The host's settings: only they can change them. " + hint
        for k, line in enumerate(wrap(hint, 56)[:3]):
            t.text(s, line, HINT[0] + 8, HINT[1] + 7 + k * 10, DIM)
        if read_only:
            m.footer("{o} back", "Esc: back")
        else:
            m.footer("{<}{>} change   {x} switch   {o} back", "Left / right: change   Enter: switch   Esc: back")
        m.show()
