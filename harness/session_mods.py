"""Co-op on top of other mods (#144): one two-game smoke test per mod disc that harness/mods.py
has built and booted. Both games run that mod's co-op disc, from its own savestates.

A mod's disc is never in the repo or in a release: mods.py makes it on this machine from the
retail disc and the mod's own tools. So only built mods register a test: `mod_<name>`, in the
--full tier (they're one more pairing of what the everyday suite covers). Run them with
`run.py -k mod_` after `mods.py --boot`.

Nothing here assumes the mod keeps retail's items, rooms or enemies: the checks compare the two
games with each other, not with retail.
"""

import tempfile
from pathlib import Path

from session import session_scenario  # first: puts `link` on the path

from bots import walker
from link.jointsave import read_session, save_room
from link.mailbox import BUSY, IN_PLAY, ROLE_AUTHORITY, ROLE_GUEST
import mods
from session_progress import (CUBE_OF_ZOE, HEART_VESSEL, HOLY_MAIL, LIFE_APPLE, LIFE_VESSEL, NO3, SHIELD_POTION,
                              arrive, counts, status, take)
from session_shared import into_hall, stage_entities

# The smoke test's own share of what each part of co-op needs. One session: cheaper than five.


def link_and_presence(run, a, b):
    bot = walker("right", attack_every=0)
    mismatches = 0
    for i in range(240):
        run.step(1, p1=(bot(a.snapshot(), i), ""))
        mismatches += a.mailbox("self_presence") != b.mailbox("partner_presence")
    run.expect(mismatches == 0, "B holds A's presence after every frame", mismatches=mismatches)
    run.expect(a.mailbox("partner_age") <= 1 and b.mailbox("partner_age") == 0, "both partners fresh")


def shared_room(run, a, b):
    """A walks into the entrance hall (session_shared.into_hall), then B arrives next to A: A is the
    room's authority, B the guest, with A's entities."""
    into_hall(run)
    roles = a.mailbox("self_presence").role, b.mailbox("self_presence").role
    run.expect(roles == (ROLE_AUTHORITY, ROLE_GUEST), "A is the room's authority, B its guest", roles=roles,
               room=a.snapshot()["room"])
    run.step(30)
    ea, eb = stage_entities(a), stage_entities(b)
    run.expect(set(ea) == set(eb) and all(ea[k][0] == eb[k][0] for k in ea),
               "B's world has exactly A's stage entities", a=len(ea), b=len(eb),
               only_a=sorted(set(ea) - set(eb))[:6], only_b=sorted(set(eb) - set(ea))[:6])


def progression(run, a, b):
    """A takes whatever the mod put at the Cube of Zoe's spot; B gets the same find. Then the castle
    flags and map agree."""
    s0a, s0b = status(a), status(b)
    arrive(run, a, NO3, *CUBE_OF_ZOE)
    run.step(300)
    s1a, s1b = status(a), status(b)
    relics_a = [i for i in range(30) if s1a["relics"][i] != s0a["relics"][i]]
    relics_b = [i for i in range(30) if s1b["relics"][i] != s0b["relics"][i]]
    found = relics_a or counts(s1a) != counts(s0a) or s1a["hp_max"] != s0a["hp_max"]
    run.expect(found, "A found something at the Cube of Zoe's spot", relics=relics_a,
               items=counts(s1a) - counts(s0a))
    run.expect(relics_a == relics_b and [s1b["relics"][i] for i in relics_b] == [s1a["relics"][i] for i in relics_a],
               "B has the same relics, found and active as for A", a=relics_a, b=relics_b)
    run.expect(counts(s1b) - counts(s0b) == counts(s1a) - counts(s0a), "B gained the same items",
               a=counts(s1a) - counts(s0a), b=counts(s1b) - counts(s0b))
    fa, fb = a.read_bytes("g_CastleFlags", 0x300), b.read_bytes("g_CastleFlags", 0x300)
    run.expect(fa == fb, "same castle flags", differ=[i for i in range(0x300) if fa[i] != fb[i]][:8])


def joint_save(run, s, a, b, path):
    s.joint.request(0)
    for _ in range(600):
        run.step(1)
        if path.exists():
            break
    run.expect(path.exists(), "the joint save was written")
    blobs = read_session(path)
    p = a.mailbox("self_presence")
    run.expect(save_room(blobs[0]) == save_room(blobs[1]) == (p.stage, p.room_left, p.room_top),
               "both saves resume in A's room", a=save_room(blobs[0]), b=save_room(blobs[1]))


def smoke(mod):
    def test(run):
        from link.jointsave import JointSave
        from session import MailboxProxy
        s, a, b = run.s, run.s.a, run.s.b
        path = Path(tempfile.mkdtemp(prefix="coop-mod-")) / "session.coop"
        s.session_file, s.joint = path, JointSave([MailboxProxy(a), MailboxProxy(b)], path)
        run.step(30)
        for g in (a, b):
            p = g.mailbox("self_presence")
            run.expect(p.flags & IN_PLAY and not p.flags & BUSY, f"game {g.name} is in play on the mod's disc")
        link_and_presence(run, a, b)
        shared_room(run, a, b)
        progression(run, a, b)
        joint_save(run, s, a, b, path)
    test.__name__ = f"mod_{mod.replace('-', '_')}"
    test.__doc__ = f"Co-op on {mod}: link, a shared room, a shared find and a joint save."
    return test


COLLECT_BASE = 0x100  # g_CastleFlags index of the first placed collectible's byte (progress.c FLAG_COLLECTIBLES)
SPOTS = (SHIELD_POTION, HOLY_MAIL, LIFE_APPLE, LIFE_VESSEL, HEART_VESSEL)  # the entrance's placed items


def gained(before, after):
    """What a player got, as collectibles.c codes: 0x8000 | hand item, 0x4000 | body item, 1 life up, 2 heart up."""
    out = [0x8000 | i for i, (x, y) in enumerate(zip(before["hand"], after["hand"])) for _ in range(y - x)]
    out += [0x4000 | i for i, (x, y) in enumerate(zip(before["body"], after["body"])) for _ in range(y - x)]
    out += [1] * ((after["hp_max"] - before["hp_max"]) // 5) + [2] * ((after["hearts_max"] - before["hearts_max"]) // 5)
    return sorted(out)


def taken(before, after):
    """Placed collectibles' flags set between two copies of g_CastleFlags."""
    return [(i - COLLECT_BASE) * 8 + k for i in range(COLLECT_BASE, len(after)) for k in range(8)
            if after[i] >> k & 1 and not before[i] >> k & 1]


def finds(mod):
    def test(run):
        """B takes the entrance's five placed finds, whatever the randomizer put there. A gets the
        same, live, as the item the randomizer placed (patcher/layer.adapt's table, made from the
        disc). Then B restarts without saving and relinks: B gets them back from A's flags."""
        import layer
        from check_disc_layout import bin_path
        a, b = run.s.a, run.s.b
        table = layer.collectibles(bin_path(mods.disc(mod)).read_bytes())
        retail = layer.collectibles(mods.RETAIL.read_bytes())
        run.step(5)
        saved, a0, b0, f0 = b.save_state(), status(a), status(b), b.read_bytes("g_CastleFlags", 0x300)
        for spot in SPOTS:
            take(run, b, spot)
        run.step(10)
        a1, b1, f1 = status(a), status(b), b.read_bytes("g_CastleFlags", 0x300)
        flags = taken(f0, f1)
        want = sorted(table[f] for f in flags if table[f])
        run.expect(gained(b0, b1) == want, "B got what the randomizer placed", flags=flags,
                   got=[hex(c) for c in gained(b0, b1)], want=[hex(c) for c in want])
        run.expect(any(table[f] != retail[f] for f in flags), "at least one of them isn't retail's item",
                   rando=[hex(table[f]) for f in flags], retail=[hex(retail[f]) for f in flags])
        run.expect(gained(a0, a1) == want, "A got the same, live", got=[hex(c) for c in gained(a0, a1)])
        b.unlink()
        b.load_state(saved)
        run.step(400)
        b.link()
        run.step(120)
        a2, b2 = status(a), status(b)
        run.expect(gained(b0, b2) == want, "back, B has them again", got=[hex(c) for c in gained(b0, b2)])
        run.expect(gained(a1, a2) == [], "A got nothing twice", got=[hex(c) for c in gained(a1, a2)])
    test.__name__ = f"rando_finds_{mod[len('rando-'):].replace('-', '_')}"
    return test


for _name in mods.MODS:
    if mods.built(_name).get("booted"):
        _cue = mods.disc(_name)
        session_scenario(starts=("entrance", "entrance"), discs=(_cue, _cue), full=True)(smoke(_name))
        if _name.startswith("rando-"):  # casual: everyday, as the randomizer's own check (D-M20)
            session_scenario(starts=("entrance", "entrance"), discs=(_cue, _cue),
                             full=_name != "rando-casual")(finds(_name))

# The control: the same test on the plain co-op disc. A mod's failure counts only where this passes.
from module import COOP_DISC  # noqa: E402

_control = smoke("none")
_control.__doc__ = "The mod tests' control: the same checks on the plain co-op disc."
session_scenario(starts=("entrance", "entrance"), discs=(COOP_DISC, COOP_DISC), full=True)(_control)
