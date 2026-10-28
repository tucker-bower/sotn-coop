"""M12 v1.0 room coverage (design/M12-v1-release.md, criterion 2; D119): Richter's and Maria's
movement envelope against Alucard's, at each step of the relic progression.

If, with the same relics, a character jumps at least as high and as far as Alucard, every room
Alucard can cross with those relics, they can cross too. The rest of a room's gates have their own
per-character tests: mist grates (m8b_mist_step), low gaps (the slide, m8b_more_gates), poison water
(m8b_poison_water), blue doors and the ferryman (they read only the relic). Measured at the castle
entrance's start, open to about 195 px above the player. Report: .env/out/<test>/relics.json."""

from link.mailbox import CHAR_MARIA, CHAR_RICHTER
from module import COOP_DISC
from scenario import scenario
from scenarios_m8 import LEAP_STONE, GRAVITY_BOOTS, SOUL_OF_BAT, RELIC_ON, STATUS, mailbox, reload_as, rise, travel
from scenarios_relics import MP, MP_MAX, report

TOLERANCE = 8  # px: a character may fall this short of Alucard (sprite and hitbox differences)
CLIMBS = 200  # px: climbing that keeps going this far counts as unlimited (the measuring spot has a
              # ceiling that Richter's backflips drift under; Alucard's bat flies up through a gap)
# Known gaps: the test passes while exactly these fall short, so a new shortfall still fails.
KNOWN = {"richter": set(), "maria": set()}  # D122's extra jumps closed the two gaps D119 found
JUMP = ["cross"] * 16 + [""] * 60
HIGH = ["down"] * 3 + [""] * 2 + ["up"] * 2 + ["up+cross"] * 2 + [""] * 60
RUN_JUMP = ["right"] * 20 + ["right+cross"] * 16 + ["right"] * 60
# Each character's own ways to use a step (scenarios_m8.m8b_more_gates for Richter's and Maria's):
# a step's distance is the best of them.
SECOND = {0: [["cross"] * 16 + [""] * 2 + ["cross"] * 12 + [""] * 60],
          CHAR_RICHTER: [["cross"] * 2 + [""] * 2 + ["cross"] * 2 + [""] * 60,      # his backflip
                         ["cross"] * 16 + [""] * 2 + ["cross"] * 2 + [""] * 60],     # ...at the top
          CHAR_MARIA: [["cross"] * 16 + [""] * 2 + ["cross"] * 12 + [""] * 60]}
THEN_SECOND = HIGH[:9] + [""] * 24 + ["cross"] * 12 + [""] * 60  # a high jump, then the second at its top
TAPS = lambda after, wait: after + [""] * wait + (["cross"] * 14 + [""] * 2) * 8 + [""] * 60  # press and hold jump, again and again: one takes
TAPPED = [TAPS(HIGH[:9], w) for w in (20, 30, 40, 50)] + [TAPS(["cross"] * 16, w) for w in (4, 8, 12)]
CLIMB = {0: [["r1"] * 2 + [""] * 30 + ["up"] * 600],
         CHAR_RICHTER: [(["cross"] * 2 + [""] * 2) * 150 + [""] * 60, (["cross"] * 2 + [""] * 6) * 75 + [""] * 60],
         CHAR_MARIA: [(["cross"] * 12 + [""] * 2) * 40 + [""] * 60, (["cross"] * 6 + [""] * 4) * 60 + [""] * 60]}


def best(r, ways):
    e = r.emu
    start, top = e.save_state(), 0
    for inputs in ways:
        e.load_state(start)
        top = max(top, rise(r, inputs))
    return top


# (step, relics, how far: (run, character) -> px)
STEPS = [
    ("jump", [], lambda r, ch: rise(r, JUMP)),
    ("running jump, distance", [], lambda r, ch: travel(r, RUN_JUMP)),
    ("second jump (Leap Stone)", [LEAP_STONE], lambda r, ch: best(r, SECOND[ch] + [JUMP] + TAPPED[4:])),
    ("high jump (Gravity Boots)", [LEAP_STONE, GRAVITY_BOOTS], lambda r, ch: best(r, [HIGH, THEN_SECOND] + SECOND[ch] + TAPPED)),
    ("climbing (Soul of Bat)", [LEAP_STONE, GRAVITY_BOOTS, SOUL_OF_BAT],
     lambda r, ch: best(r, CLIMB[ch] + [HIGH, THEN_SECOND])),
]


def envelope(run, ch):
    e = run.emu
    start = e.save_state()
    out = []
    for name, relics, how in STEPS:
        e.load_state(start)
        for r in relics:
            e.write(STATUS, RELIC_ON, "<B", r)
        e.write(MP, e.read(MP_MAX, "<i"), "<i")
        run.step(60)  # settled: standing, ready to jump
        out.append(how(run, ch))
    return out


def _test(ch, name):
    def test(run):
        mb = mailbox(run)
        start = run.emu.save_state()
        reload_as(run, mb, 0)  # the same spot for everyone: where a load puts the player
        alucard = envelope(run, 0)
        run.emu.load_state(start)
        reload_as(run, mb, ch)
        theirs = envelope(run, ch)
        rows = [{"step": s[0], "alucard": a, name: t,
                 "ok": t >= a - TOLERANCE or (s[0].startswith("climbing") and t >= CLIMBS)}
                for s, a, t in zip(STEPS, alucard, theirs)]
        report(run, rows)
        bad = [r for r in rows if not r["ok"] and r["step"] not in KNOWN[name]]
        fixed = [r["step"] for r in rows if r["ok"] and r["step"] in KNOWN[name]]
        run.expect(not fixed, "a known gap is closed: take it off KNOWN", fixed=fixed)
        run.expect(not bad, f"{name.capitalize()} reaches as high and as far as Alucard at every relic step", bad=bad)
    test.__name__ = f"m12_envelope_{name}"
    test.__doc__ = __doc__.split("\n\n")[0]
    scenario(start="entrance", disc=COOP_DISC)(test)


_test(CHAR_RICHTER, "richter")
_test(CHAR_MARIA, "maria")
