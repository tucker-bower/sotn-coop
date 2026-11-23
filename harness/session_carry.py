"""Hanging onto Bat Alucard (design/bat-carry.md): a castle rule, in two real games."""

from link.mailbox import BUSY, CHAR_RICHTER, FLIP_BAT, FLIP_CARRIED, RULE_BAT_CARRY
from module import symbols
from session import session_scenario
from session_m15 import load_characters
from session_progress import arrive
from session_rules import rules
from session_shared import HALL, into_hall

SOUL_OF_BAT = 0x80097964  # g_Status.relics[0]
ACTIVE = 3
FLIGHT = 20
DOOR_Y = 124


def flips(g):
    return g.mailbox("self_presence").flip_x


def place(g):
    s = g.snapshot()
    return s["world_x"], s["world_y"]


def bat(run, g):
    """g turns into a bat and rises off the floor. Both have the relic, as in a real castle: one
    only g has is sent to the partner as a find (#356), mid-test."""
    for each in run.s.games:
        each.write(SOUL_OF_BAT, ACTIVE, "<B")
    run.step(5)
    pads = lambda pad: (pad, "") if g is run.s.a else ("", pad)
    run.step(4, p1=pads("r1"))
    run.step(40)
    run.step(FLIGHT, p1=pads("up"))
    run.expect(flips(g) & FLIP_BAT, "it's a bat, in flight", flip=flips(g))


def alongside(run, carrier, rider):
    """The rider stands under the bat, within reach."""
    p = carrier.mailbox("self_presence")
    x, y = place(carrier)
    for _ in range(2):
        rider_x = place(rider)[0]
        if abs(rider_x - x) <= 24:
            break
        arrive(run, rider, p.stage, p.room_id, x, p.ground_y)
        run.step(30)


def grab(run, carrier, rider):
    pad = lambda pad: ("", pad) if rider is run.s.b else (pad, "")
    run.step(3, p1=pad("up"))
    run.step(3)
    run.expect(flips(rider) & FLIP_CARRIED, "the rider hangs on", flip=flips(rider), bat=place(carrier),
               rider=place(rider))


def setup(run, swap=False):
    a, b = run.s.a, run.s.b
    load_characters(run)
    rules(run, RULE_BAT_CARRY)
    into_hall(run)
    run.expect(a.snapshot()["room"] == b.snapshot()["room"], "both in the hall")
    carrier, rider = (b, a) if swap else (a, b)
    bat(run, carrier)
    alongside(run, carrier, rider)


def carried_flight(run, swap=False, slack=40):
    a, b = run.s.a, run.s.b
    setup(run, swap)
    carrier, rider = (b, a) if swap else (a, b)
    grab(run, carrier, rider)
    worst, far = 0, 0
    x0 = place(rider)[0]
    for i in range(90):
        pad = "right+up" if i < 30 else "right"
        run.step(1, p1=("", pad) if swap else (pad, ""))
        cx, cy = place(carrier)
        rx, ry = place(rider)
        worst = max(worst, abs(cx - rx), abs(cy - ry))
        far = max(far, abs(rx - x0))
    run.expect(flips(rider) & FLIP_CARRIED, "still carried")
    run.expect(far >= 30, "the rider was carried across", far=far)
    run.expect(worst <= slack, "the rider stayed with the bat", worst=worst)


@session_scenario()
def bat_carry_alucard(run):
    """Two Alucards: B hangs on, and is carried."""
    carried_flight(run)


def carry_through_a_door(run):
    a, b = run.s.a, run.s.b
    setup(run)
    grab(run, a, b)
    for _ in range(1500):  # the hall's east door is at this height, above the stairs
        y = place(a)[1]
        run.step(1, p1=("right+up" if y > DOOR_Y else "right+down" if y < DOOR_Y - 8 else "right", ""))
        if a.snapshot()["room"] != b.snapshot()["room"] or a.snapshot()["room"] != HALL:
            break
    run.expect(a.snapshot()["room"] != HALL, "the bat left the hall", room=a.snapshot()["room"])
    for _ in range(400):
        run.step(1, p1=("right", ""))
        if a.snapshot()["room"] == b.snapshot()["room"] and not b.mailbox("self_presence").flags & BUSY:
            break
    run.step(60)
    run.expect(a.snapshot()["room"] == b.snapshot()["room"], "both players end up in the same room",
               a=a.snapshot()["room"], b=b.snapshot()["room"])


# What each game draws of the other (#262): the partner's copy, its entity 0 first.
BODY_X, BODY_Y, BODY_ANIM_SET = 2, 6, 0x54
ANIM_SET_BAT = 13


def body(g, field, fmt="<h"):
    return g.read(symbols()["g_CoopSpikeBody"] + field, fmt)


def both_have_the_bat(run):
    """As in a real castle: a relic found by one is given to both (progress.c)."""
    run.s.b.write(SOUL_OF_BAT, ACTIVE, "<B")


@session_scenario(characters=(0, CHAR_RICHTER))
def bat_carry_rider_hangs_in_the_bats_game(run):
    """In the bat's game, the carried Richter is drawn hanging under the bat, where his own game has
    him, not walking along the floor below it (zhika, 1.0.0)."""
    a, b = run.s.a, run.s.b
    both_have_the_bat(run)
    setup(run)
    grab(run, a, b)
    worst = 0
    for i in range(90):
        run.step(1, p1=("right+up" if i < 30 else "right", ""))
        p = a.mailbox("self_presence")
        seen = (body(a, BODY_X) + p.scroll_x, body(a, BODY_Y) + p.scroll_y)
        if i >= 10:
            worst = max(worst, abs(seen[0] - place(b)[0]), abs(seen[1] - place(b)[1]))
    run.expect(flips(b) & FLIP_CARRIED, "still carried")
    run.expect(worst <= 8, "the bat's game draws him where he hangs", worst=worst, seen=seen, rider=place(b))


@session_scenario(characters=(0, CHAR_RICHTER))
def bat_carry_through_a_door_still_a_bat(run):
    """Carried through a door, Richter's game still draws Alucard as a bat: the copy it makes of him
    in the new room starts on foot, and takes his form (zhika, 1.0.0: Alucard mid-jump, torn)."""
    a, b = run.s.a, run.s.b
    both_have_the_bat(run)
    carry_through_a_door(run)
    run.step(30, p1=("up", ""))
    run.expect(flips(a) & FLIP_BAT, "Alucard is still a bat", flip=flips(a))
    run.expect(body(b, BODY_ANIM_SET) == ANIM_SET_BAT, "Richter's game draws him as a bat",
               anim_set=body(b, BODY_ANIM_SET),
               forms=b.read(symbols()["g_CoopBodyForms"], "<I") if "g_CoopBodyForms" in symbols() else None)
