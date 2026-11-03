"""Hanging onto Bat Alucard (design/bat-carry.md): a castle rule, in two real games."""

from link.mailbox import BUSY, CHAR_RICHTER, FLIP_BAT, FLIP_CARRIED, RULE_BAT_CARRY
from session import session_scenario
from session_m15 import load_characters
from session_netplay import PROFILE, SEED
from session_progress import HP, STATUS, arrive
from session_rules import rules
from session_shared import HALL, into_hall

SOUL_OF_BAT = 0x80097964  # g_Status.relics[0]
ACTIVE = 3
FLIGHT = 20
VRAM_FLAG = 0x80072F20  # g_Player.vram_flag
DOOR_Y = 124


def flips(g):
    return g.mailbox("self_presence").flip_x


def place(g):
    s = g.snapshot()
    return s["world_x"], s["world_y"]


def bat(run, g):
    """g turns into a bat and rises off the floor."""
    g.write(SOUL_OF_BAT, ACTIVE, "<B")
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


@session_scenario(characters=(0, CHAR_RICHTER))
def bat_carry_richter(run):
    """Richter hangs onto Alucard's bat, and is carried."""
    carried_flight(run)


@session_scenario()
def bat_carry_other_seat(run):
    """The guest is the bat, and the room's authority hangs on."""
    carried_flight(run, swap=True)


@session_scenario()
def bat_carry_on_a_bad_connection(run):
    """The carried player trails by the round trip, with jitter, and still stays with the bat."""
    run.s.set_net(PROFILE, SEED)
    carried_flight(run, slack=60)


@session_scenario()
def bat_carry_off_by_default(run):
    """With the rule off the presence bit stays clear, and Up beside the bat does nothing."""
    a, b = run.s.a, run.s.b
    into_hall(run)
    a.write(SOUL_OF_BAT, ACTIVE, "<B")
    run.step(5)
    run.step(4, p1=("r1", ""))
    run.step(40)
    run.step(FLIGHT, p1=("up", ""))
    run.expect(not flips(a) & FLIP_BAT, "no bat offered", flip=flips(a))
    run.step(3, p1=("", "up"))
    run.step(3)
    run.expect(not flips(b) & FLIP_CARRIED, "not carried")


@session_scenario()
def bat_carry_is_slower(run):
    """The bat covers about 60% of the ground while carrying, and all of it after."""
    a, b = run.s.a, run.s.b
    setup(run)

    def flight(pad):
        x0 = place(a)[0]
        run.step(30, p1=(pad, ""))
        return abs(place(a)[0] - x0)
    run.step(20, p1=("right", ""))  # up to speed
    free = flight("right")
    run.step(45, p1=("left", ""))
    alongside(run, a, b)
    grab(run, a, b)
    run.step(20, p1=("right", ""))
    carrying = flight("right")
    run.expect(0.45 * free <= carrying <= 0.75 * free, "about 60% of the speed", free=free, carrying=carrying)
    run.step(3, p1=("", "cross"))
    run.step(3)
    run.step(45, p1=("left", ""))
    run.step(20, p1=("right", ""))
    after = flight("right")
    run.expect(after >= 0.9 * free, "full speed after", free=free, after=after)


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


@session_scenario()
def bat_carry_through_a_door(run):
    """The bat flies out of the hall: its passenger comes too, carried or by the teleport path."""
    carry_through_a_door(run)


def released(run, rider, what):
    run.step(4)
    run.expect(not flips(rider) & FLIP_CARRIED, what, flip=flips(rider))
    run.step(180)
    run.expect(rider.read(VRAM_FLAG, "<i") & 1, "they land on solid ground", place=place(rider))


@session_scenario()
def bat_carry_jump_drops_off(run):
    a, b = run.s.a, run.s.b
    setup(run)
    grab(run, a, b)
    run.step(30, p1=("up", ""))
    run.step(2, p1=("", "cross"))
    released(run, b, "Cross lets go")


@session_scenario()
def bat_carry_a_hit_drops_off(run):
    a, b = run.s.a, run.s.b
    setup(run)
    grab(run, a, b)
    run.step(10)
    b.write(STATUS, b.read(STATUS, "<i", HP) - 5, "<i", HP)
    released(run, b, "a hit lets go")


@session_scenario()
def bat_carry_landing_drops_off(run):
    a, b = run.s.a, run.s.b
    setup(run)
    grab(run, a, b)
    run.step(120, p1=("down", ""))
    released(run, b, "the bat on the ground lets go")


@session_scenario()
def bat_carry_form_change_drops_off(run):
    a, b = run.s.a, run.s.b
    setup(run)
    grab(run, a, b)
    run.step(30, p1=("up", ""))
    run.step(4, p1=("r1", ""))
    run.step(30)
    released(run, b, "the bat turning back lets go")
