"""M13 spike (design/M13-partner-player.md): the partner simulated by the game's own player code,
in one game, driven by scripted buttons (module/partner.c, OPT_PARTNER_SIM). Measures what the
spike must answer: the partner moves as its buttons say, player 1 is untouched, the frame cost,
and determinism."""

import struct
from pathlib import Path

from module import symbols

PAD = {"": 0, "right": 0x2000, "left": 0x8000, "cross": 0x40}  # PAD_* (include/game.h)


# --- the partner's body in a two-game session ------------------------------------------------
from session import session_scenario  # noqa: E402
from session_progress import status  # noqa: E402
from link.mailbox import CHAR_ALUCARD, CHAR_MARIA, CHAR_RICHTER  # noqa: E402


@session_scenario(starts=("entrance", "entrance"))
def partner_body_follows(run):
    """Game A simulates B's body from B's buttons (played out with B's presence) while B walks
    and jumps around the room: A's copy stays with B's real spot (within the snap distance), and
    A's own player is untouched; no puppet is drawn while the body is."""
    from link.mailbox import OPT_PARTNER_SIM
    a, b = run.s.a, run.s.b
    a.host("set_player", options=OPT_PARTNER_SIM)
    body = symbols()["g_CoopSpikeBody"]
    run.step(30)
    worst, samples = 0, 0
    pattern = ["right"] * 60 + ["right+cross"] * 14 + ["right"] * 40 + ["left"] * 80 + ["left+cross"] * 14 + [""] * 40
    for t, pad in enumerate(pattern * 2):
        run.step(1, ("", pad))
        if t % 10 == 0:
            raw = a.read_bytes(body, 0xBC)
            bx = struct.unpack_from("<h", raw, 2)[0] + a.read("g_Tilemap", "<h", 0x0A)  # + scrollX.i.hi
            sb = b.snapshot()
            if sb["room"] == a.snapshot()["room"]:
                worst = max(worst, abs(bx - sb["world_x"]))
                samples += 1
    run.expect(samples > 20 and worst <= 48, "A's copy of B stays with B (within the snap distance)",
               worst_px=worst, samples=samples)
    run.expect(a.snapshot()["hp"] > 0, "A plays on")


def _partner_pair(run, ca, cb):
    """A plays ca and B plays cb (both from a reload); A runs B's body with B's partner build: it's
    B's character (B's animation set), follows and animates, and A stays itself."""
    from link.mailbox import OPT_PARTNER_SIM
    from session_m8 import reload_game
    a, b = run.s.a, run.s.b
    for g, c in ((a, ca), (b, cb)):
        run.expect(reload_game(run, g) and g.mailbox("self_presence").character == c, f"{'AB'[g is b]} plays {c}")
    run.step(60)
    mine = a.read("g_Entities", "<h", 0x54), a.read(0x80280020)
    a.host("set_player", options=OPT_PARTNER_SIM)
    run.step(30)
    body = symbols()["g_CoopSpikeBody"]
    poses, worst, samples = set(), 0, 0
    pattern = ["right"] * 60 + ["right+cross"] * 14 + ["right"] * 40 + ["left"] * 80 + ["left+square"] * 20 + [""] * 40
    for t, pad in enumerate(pattern):
        run.step(1, ("", pad))
        poses.add(a.read(body, "<H", 0x56))
        if t % 10 == 0:
            bx = a.read(body, "<h", 2) + a.read("g_Tilemap", "<h", 0x0A)
            sb = b.snapshot()
            if sb["room"] == a.snapshot()["room"]:
                worst = max(worst, abs(bx - sb["world_x"]))
                samples += 1
        if t == 200:
            shots = Path(__file__).resolve().parent.parent / ".env/out/shots"
            shots.mkdir(parents=True, exist_ok=True)
            a.screenshot().save(shots / f"m13_partner_{ca}{cb}.png")
    run.expect(a.read(body, "<h", 0x54) == b.read("g_Entities", "<h", 0x54), "A's copy of B has B's animation set")
    if cb == CHAR_ALUCARD and ca != CHAR_ALUCARD:  # his body's palette, in A's second bank, as in B's game
        cid = a.read("g_ClutIds", "<H", 2 * (a.read(body, "<H", 0x16) & 0x7FFF))
        x, y = (cid & 0x3F) * 16, (cid >> 6) & 0x1FF
        run.expect(a.vram_rect(x, y + 512, 16, 1) == b.vram_rect(x, y, 16, 1),
                   "Alucard's palette is in A's second bank, as in his own game")
    run.expect(samples > 10 and worst <= 48, "A's copy follows B", worst_px=worst, samples=samples)
    run.expect(len(poses) > 8, "and animates", poses=len(poses))
    run.expect((a.read("g_Entities", "<h", 0x54), a.read(0x80280020)) == mine and a.snapshot()["hp"] > 0,
               "A is still its own character, in play")


LIFE_APPLE = 0x26 + 0x92  # g_Status.equipHandCount[ITEM_LIFE_APPLE], from g_Status


# --- criterion 2: the partner's attacks, drawn by the game's own code, for all 9 pairings --------


