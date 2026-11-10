"""A castle's rules (D162, design/M-castle-rules.md): everything co-op changes about the game, as a
setting of the castle it's played in. They live in castle.json, a joiner's copy gets the host's,
and the host's game and the joiner's run on the same ones.

Every rule in RULES has a default, which is how the game plays without touching anything. A castle
stores only what it has, so a rule added later takes its default in old castles. encode() is what
the game gets (the mailbox's rule words, link/mailbox.py); with every rule at its default all of
them are zero, so a game with no rules set plays the same.
"""

from link.mailbox import (OPT_NO_AIR_JUMPS, OPT_NO_ALUCARD_STATS, OPT_NO_GROWTH, OPT_NO_RELIC_MOVES, RULE_BAT_CARRY, RULE_NO_BOSS_PULL,
                          RULE_NO_FAERIE_REVIVE, RULE_NO_FAMILIARS, RULE_NO_GEAR_EFFECTS, RULE_NO_MAP_TELEPORT, RULE_NO_NEAR_TARGET,
                          RULE_NO_OFFHAND, RULE_NO_REVIVE, RULE_NO_SCENE_PULL, RULE_NO_SHARED_GOLD,
                          RULE_NO_SHARED_LEVEL)

# (id, label, hint, default, min, max, step): a slider, in %
SLIDERS = (
    ("exp_pct", "XP gain", "XP from each kill. With a shared level, it's then split between you", 100, 25, 400, 25),
    ("taken_pct", "Damage taken", "The damage enemies do to you, after your defense", 100, 25, 400, 25),
    ("enemy_hp_pct", "Enemy HP, with a partner", "All enemies' and bosses' HP when a partner is connected: 100% is the game's own", 200, 50, 400, 25),
    ("enemy_hp_solo_pct", "Enemy HP, alone", "All enemies' and bosses' HP with no partner: 100% is the game's own", 100, 50, 400, 25),
    ("aggro", "Boss aggro", "A boss's chance to switch to the other player, every 3 s", 50, 0, 100, 10),
)
# (id, label, hint, default, the rule's bit when it's off)
TOGGLES = (
    ("shared_level", "One shared level", "On: a kill's XP is split and goes to you both. Off: each of you levels alone",
     True, RULE_NO_SHARED_LEVEL),
    ("shared_gold", "One purse", "On: gold is shared. Off: each of you has your own", True, RULE_NO_SHARED_GOLD),
    ("revive", "Revive at your partner", "Off: a fallen player stays down; when both fall, back to the last save",
     True, RULE_NO_REVIVE),
    ("faerie_revive", "Partner's faerie revives", "A partner's faerie uses a Life Apple to revive you where you fell",
     True, RULE_NO_FAERIE_REVIVE),
    ("boss_pull", "Bosses bring your partner", "A boss fight teleports the other player in", True, RULE_NO_BOSS_PULL),
    ("scene_pull", "Scenes bring your partner", "A story scene teleports the other player in", True, RULE_NO_SCENE_PULL),
    ("map_teleport", "Teleport from the map", "Cross on the map goes to your partner", True, RULE_NO_MAP_TELEPORT),
    ("near_target", "Enemies pick the nearer player", "Off: in a shared room, enemies only aim at its first player",
     True, RULE_NO_NEAR_TARGET),
    ("growth", "Richter and Maria level up", "XP gives them levels, with Alucard's HP, hearts and stats for each",
     True, OPT_NO_GROWTH),
    ("alucard_stats", "Richter and Maria use Alucard's stats",
     "Their attacks do Alucard's damage a second and grow with STR and INT; defense, armour and resistances cut the "
     "damage they take; poison and poisoned water hurt them, as for Alucard. "
     "Off: their attacks and the damage they take are their own games'", True, OPT_NO_ALUCARD_STATS),
    ("relic_moves", "Relics teach Richter and Maria", "Off: they know every move from the start",
     True, OPT_NO_RELIC_MOVES),
    ("air_jumps", "Extra jumps", "Richter's and Maria's jumps from the Leap Stone and Gravity Boots. "
     "Off: parts of the castle may be out of reach", True, OPT_NO_AIR_JUMPS),
    ("offhand", "Off-hand weapons", "Richter and Maria: Circle uses the item in the other hand", True, RULE_NO_OFFHAND),
    ("familiars", "Richter's and Maria's familiars", "Their familiar cards work, as Alucard's do", True, RULE_NO_FAMILIARS),
    ("gear_effects", "Richter's and Maria's gear effects", "Healing Mail heals them as they walk, and the Blood Cloak "
     "gives hearts for damage, as for Alucard", True, RULE_NO_GEAR_EFFECTS),
    ("bat_carry", "Hang onto the bat", "Up beside Alucard's bat hangs on, and it flies slower. Cross drops off", False, 0),
    ("pvp", "PvP", "Your attacks hurt each other", False, 0),
    ("remap", "Button remap", "Both players' buttons follow the map below", False, 0),
)
REMAP_BUTTONS = ("cross", "circle", "square", "triangle", "l1", "r1", "l2", "r2")
BUTTON_NAMES = {"cross": "Cross", "circle": "Circle", "square": "Square", "triangle": "Triangle",
                "l1": "L1", "r1": "R1", "l2": "L2", "r2": "R2"}
DEFAULTS = {**{s[0]: s[3] for s in SLIDERS}, **{t[0]: t[3] for t in TOGGLES}, "remap_map": {}}
# Difficulty (design/launcher-overhaul.md, Tucker 2026-11-10): what each sets, at once. It isn't
# stored: a castle's difficulty is whichever of these its four values match, else "Custom". Enemies
# alone have half the HP they have with a partner, so Medium alone is the original game. There is
# no "damage dealt": more enemy HP does the same without the player's numbers going down.
DIFFICULTIES = (
    ("Easy", {"enemy_hp_pct": 100, "enemy_hp_solo_pct": 50, "taken_pct": 50, "exp_pct": 150}),
    ("Medium", {"enemy_hp_pct": 200, "enemy_hp_solo_pct": 100, "taken_pct": 100, "exp_pct": 100}),
    ("Hard", {"enemy_hp_pct": 300, "enemy_hp_solo_pct": 150, "taken_pct": 150, "exp_pct": 50}),
    ("Nightmare", {"enemy_hp_pct": 400, "enemy_hp_solo_pct": 200, "taken_pct": 200, "exp_pct": 50}),
)
CUSTOM = "Custom"
# The settings screen's groups, in order: (heading, the rules under it)
GROUPS = (
    ("Balance", ("enemy_hp_pct", "enemy_hp_solo_pct", "taken_pct", "exp_pct", "aggro")),
    ("Sharing", ("shared_level", "shared_gold")),
    ("Falling and reviving", ("revive", "faerie_revive")),
    ("Staying together", ("boss_pull", "scene_pull", "map_teleport", "near_target")),
    ("Richter and Maria", ("growth", "alucard_stats", "relic_moves", "air_jumps", "offhand", "familiars", "gear_effects")),
    ("Extras", ("bat_carry", "pvp", "remap")),
)


def difficulty(rules):
    """ "Easy", "Medium", "Hard", "Nightmare", or "Custom" when the four values match none of them."""
    return next((name for name, sets in DIFFICULTIES if all(rules.get(k) == v for k, v in sets.items())), CUSTOM)


def set_difficulty(rules, name):
    """Sets what that difficulty sets (an unknown name: nothing)."""
    rules.update(dict(DIFFICULTIES).get(name, {}))


def next_difficulty(rules, step):
    """The difficulty one step up or down from the castle's; from Custom, Medium."""
    names = [n for n, _ in DIFFICULTIES]
    now = difficulty(rules)
    return "Medium" if now == CUSTOM else names[max(0, min(len(names) - 1, names.index(now) + step))]


def clean(stored):
    """Every rule, from what a castle (or a partner) has: anything missing or out of range takes
    its default, anything unknown goes."""
    stored = stored if isinstance(stored, dict) else {}
    out = dict(DEFAULTS)
    for key, _, _, _, low, high, _ in SLIDERS:
        v = stored.get(key)
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[key] = max(low, min(high, int(v)))
    for t in TOGGLES:
        if isinstance(stored.get(t[0]), bool):
            out[t[0]] = stored[t[0]]
    if "alucard_stats" not in stored and stored.get("growth") is False:
        out["alucard_stats"] = False  # a castle from before the split: growth was both
    remap = stored.get("remap_map")
    if isinstance(remap, dict):
        out["remap_map"] = {a: b for a, b in remap.items() if a in REMAP_BUTTONS and b in REMAP_BUTTONS and a != b}
    return out


def for_castle(castle, settings=None):
    """A castle's rules. One from before they were a castle's (D162) starts from the app's old
    global PvP, aggro and enemy health settings."""
    stored = castle.info.get("rules") if castle is not None else None
    if stored is None:
        return legacy(settings)
    return clean(stored)


def legacy(settings):
    settings = settings or {}
    out = {k: settings[k] for k in ("pvp", "aggro") if k in settings}
    if "enemy_hp" in settings:
        out["enemy_hp_pct"] = settings["enemy_hp"]
    return clean(out)


def encode(rules):
    """What the game gets: (the RULE_* / OPT_NO_* bits, exp, dealt, taken, enemy HP, enemy HP alone),
    the percentages 0 at their defaults."""
    rules = clean(rules)
    off = 0
    for key, _, _, _, bit in TOGGLES:
        if bit and not rules[key]:
            off |= bit
    if rules["bat_carry"]:
        off |= RULE_BAT_CARRY

    def pct(key):
        return 0 if rules[key] == DEFAULTS[key] else rules[key]
    # (the game also takes a "damage dealt" percentage: no rule sets it any more, so it's the default)
    return (off, pct("exp_pct"), 0, pct("taken_pct"), pct("enemy_hp_pct"), pct("enemy_hp_solo_pct"))


def remapped(pad, rules):
    """A pad ("circle+left", as gameview.Pads.mask gives) through the castle's button remap."""
    if not rules.get("remap") or not pad:
        return pad
    table = rules.get("remap_map") or {}
    return "+".join(sorted({table.get(b, b) for b in pad.split("+")}))


def next_target(rules, button):
    """The next choice for a button in the remap editor: its own, then each of the others."""
    now = rules["remap_map"].get(button, button)
    return REMAP_BUTTONS[(REMAP_BUTTONS.index(now) + 1) % len(REMAP_BUTTONS)]


def set_target(rules, button, target):
    """Maps a button (to itself: no entry)."""
    rules["remap_map"].pop(button, None)
    if target != button:
        rules["remap_map"][button] = target


def changed(rules):
    """The labels of what differs from the defaults, for a line in a lobby or the castle list."""
    rules = clean(rules)
    return [s[1] for s in SLIDERS if rules[s[0]] != s[3]] + [t[1] for t in TOGGLES if rules[t[0]] != t[3]]
