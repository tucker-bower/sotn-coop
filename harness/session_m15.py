"""M15 (design/M15-pvp.md): PvP, the host's option. The victim's game decides each hit from the
attacker's hitboxes (module/pvp.c, D132); its player's own damage code does the rest."""

from link.mailbox import CHAR_ALUCARD, CHAR_MARIA, CHAR_RICHTER, CONTROL_PVP, OPT_PARTNER_SIM
from module import symbols
from session import session_scenario
from session_progress import status

STEP_HIT = 10  # PLAYER.step of a hit reaction (Alucard's, Richter's and Maria's)


def pvp_hits(g):
    return g.read(symbols()["g_CoopPvpHits"])


def player_step(g):
    return g.read("g_Entities", "<H", 0x2C)


def apart(run, gap=24):
    """A walks left until it's `gap` px left of B (both start on the same spot; right of it, the
    ground drops)."""
    a, b = run.s.a, run.s.b
    for _ in range(120):
        if b.snapshot()["world_x"] - a.snapshot()["world_x"] >= gap:
            break
        run.step(1, p1=("left", ""))
    run.step(10)
    run.expect(a.snapshot()["world_y"] == b.snapshot()["world_y"], "A and B stand on the same ground",
               a=(a.snapshot()["world_x"], a.snapshot()["world_y"]), b=(b.snapshot()["world_x"], b.snapshot()["world_y"]))


def attack(run, pad, frames=90, every=20):
    """A presses `pad` (with right held, facing B) every `every` frames; returns B's PvP hits, its
    HP drop, the steps it went through and how far it moved."""
    a, b = run.s.a, run.s.b
    hits0, hp0, x0 = pvp_hits(b), status(b)["hp"], b.snapshot()["world_x"]
    steps = set()
    for i in range(frames):
        run.step(1, p1=(pad if i % every < 2 else "", ""))
        steps.add(player_step(b))
    return {"hits": pvp_hits(b) - hits0, "hp": hp0 - status(b)["hp"], "steps": sorted(steps),
            "moved": b.snapshot()["world_x"] - x0, "a_body_hits": a.read(symbols()["g_CoopBodyHits"])}


def setup(run, pvp=True):
    a, b = run.s.a, run.s.b
    for g in (a, b):
        g.mailbox("set_control", CONTROL_PVP if pvp else 0)
        g.host("set_player", options=OPT_PARTNER_SIM)
    run.step(200)  # past the first 3 s in the room (spawn protection)
    apart(run)


def _sword(run):
    """Criteria 1-2, a hand weapon: A swings at B. B is hit by its own damage code (its HP drops,
    by less than the attack: its defence), staggers (its hit step) and is knocked away from A;
    A's copy of B shows the hit too."""
    a, b = run.s.a, run.s.b
    setup(run)
    body0 = a.read(symbols()["g_CoopBodyHits"])
    r = attack(run, "right+square")
    run.expect(r["hits"] > 0, "B's game took A's swing", **r)
    run.expect(r["hp"] > 0, "B lost HP", **r)
    run.expect(STEP_HIT in r["steps"], "B staggered (its hit step)", **r)
    run.expect(r["moved"] > 0, "B was knocked away from A (right)", **r)
    run.expect(r["a_body_hits"] > body0, "A's copy of B was hit too", **r)


@session_scenario(starts=("entrance", "entrance"))
def m15_pvp_sword_aa(run):
    _sword(run)


@session_scenario(starts=("entrance", "entrance"), characters=(CHAR_RICHTER, CHAR_ALUCARD))
def m15_pvp_whip_ra(run):
    _sword(run)


@session_scenario(starts=("entrance", "entrance"), characters=(CHAR_MARIA, CHAR_RICHTER))
def m15_pvp_maria_mr(run):
    _sword(run)


@session_scenario(starts=("entrance", "entrance"))
def m15_pvp_off(run):
    """Criterion 3: PvP off (the default), the same swings do nothing."""
    setup(run, pvp=False)
    r = attack(run, "right+square")
    run.expect(r["hits"] == 0 and r["hp"] == 0, "no PvP hit, no HP lost", **r)
