"""A castle's rules (D162), no games run: the defaults change nothing, each castle keeps its own, a
joiner's copy takes the host's, and castles from before rules keep what the app was set to.

    python launcher/test_rules.py
"""
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

failures = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def main():
    import rules
    check(rules.encode({}) == (0, 0, 0, 0, 0, 0), "the defaults give the game all zeros: it plays as it always has")
    check(rules.DEFAULTS["enemy_hp_pct"] == 200 and rules.DEFAULTS["enemy_hp_solo_pct"] == 100 and rules.DEFAULTS["aggro"] == 50,
          "boss HP 2x with a partner, 1x alone, 50% aggro")
    check(rules.DEFAULTS["pvp"] is False and rules.DEFAULTS["remap"] is False, "PvP and the button remap start off")
    check(all(t[3] for t in rules.TOGGLES if t[0] not in ("pvp", "remap", "bat_carry")), "every other toggle starts on, as the game plays now")
    check(rules.changed({}) == [], "nothing differs from the defaults")
    check(rules.encode({"bat_carry": True})[0] == rules.RULE_BAT_CARRY, "bat carry on sets its bit")
    bits = [t[4] for t in rules.TOGGLES if t[4]]
    check(len(bits) == len(set(bits)) and all(b and not b & (b - 1) for b in bits), "each rule has a bit of its own")
    for t in rules.TOGGLES:
        if t[4]:
            check(rules.encode(dict(rules.clean({}), **{t[0]: False}))[0] == t[4], f"{t[0]} off sets its bit")
    old = rules.clean({"growth": False})
    check(not old["growth"] and not old["alucard_stats"], "a castle from before Alucard's stats had its own rule: growth off was both")
    check(rules.clean({"growth": False, "alucard_stats": True})["alucard_stats"], "levels off, Alucard's stats on: each is its own")
    check(rules.encode({"exp_pct": 200, "dealt_pct": 50, "taken_pct": 75, "enemy_hp_pct": 100, "enemy_hp_solo_pct": 300}) ==
          (0, 200, 50, 75, 100, 300), "each slider reaches the game")
    check(rules.clean({"exp_pct": 100000, "aggro": -5})["exp_pct"] == 400 and rules.clean({"aggro": -5})["aggro"] == 0,
          "sliders stay in range")
    check(rules.clean({"pvp": "yes", "unknown": 1})["pvp"] is False and "unknown" not in rules.clean({"unknown": 1}),
          "a partner's junk is ignored")
    check(all(s[4] > 0 for s in rules.SLIDERS if s[0] != "aggro"), "no percent reaches 0 (0 means the default)")

    swap = {"remap": True, "remap_map": {"circle": "square", "square": "circle"}}
    check(rules.remapped("circle+left", swap) == "left+square", "the remap changes the buttons it maps")
    check(rules.remapped("square+circle", swap) == "circle+square", "a swap goes both ways at once")
    check(rules.remapped("circle", dict(swap, remap=False)) == "circle", "off, the pad is as it was")
    check(rules.remapped("", swap) == "", "nothing pressed stays nothing pressed")
    r = rules.clean({})
    seen = []
    for _ in rules.REMAP_BUTTONS:
        rules.set_target(r, "cross", rules.next_target(r, "cross"))
        seen.append(r["remap_map"].get("cross", "cross"))
    check(seen[-1] == "cross" and "cross" not in r["remap_map"] and len(set(seen)) == len(rules.REMAP_BUTTONS),
          "the remap editor goes through every button and back")

    with tempfile.TemporaryDirectory() as d:
        os.environ["COOP_DATA"] = d
        from archive import Castle
        a, b = Castle.new(name="A"), Castle.new(name="B")
        check(rules.for_castle(a) == rules.clean({}), "a new castle has the defaults")
        a.set_rules(rules.clean({"exp_pct": 200, "pvp": True}))
        check(rules.for_castle(Castle(a.dir))["exp_pct"] == 200, "a castle's rules are saved with it")
        check(rules.for_castle(Castle(b.dir))["exp_pct"] == 100, "another castle's are its own")
        check(rules.for_castle(None) == rules.clean({}), "no castle (a debug start): the defaults")
        check(rules.for_castle(b, {"pvp": True, "aggro": 70})["pvp"] is True and
              rules.for_castle(b, {"pvp": True, "aggro": 70})["aggro"] == 70,
              "a castle from before rules keeps the app's old PvP and aggro settings")
        check(rules.for_castle(a, {"pvp": False, "aggro": 70})["pvp"] is True, "a castle's own rules win over those")
        host = rules.clean({"taken_pct": 150, "shared_gold": False})
        copy = Castle.receive(a.meta())
        copy.set_rules(host)
        check(rules.for_castle(Castle(copy.dir)) == host and copy.info["id"] == a.info["id"],
              "a joiner's copy holds the host's rules")
        check(rules.for_castle(Castle(a.dir))["exp_pct"] == 200, "and the castle it was copied from is untouched")
    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
