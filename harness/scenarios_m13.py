"""M13 spike (design/M13-partner-player.md): the partner simulated by the game's own player code,
in one game, driven by scripted buttons (module/partner.c, OPT_PARTNER_SIM). Measures what the
spike must answer: the partner moves as its buttons say, player 1 is untouched, the frame cost,
and determinism."""

import struct
from pathlib import Path

from link.mailbox import OPT_PARTNER_SIM
from module import COOP_DISC, symbols
from scenario import scenario
from scenarios_m8 import mailbox

PAD = {"": 0, "right": 0x2000, "left": 0x8000, "cross": 0x40}  # PAD_* (include/game.h)
SCANLINES = 263  # NTSC: a frame


def body_x(e):
    """The partner's entity 0 (the first thing in its copy): world x."""
    raw = e.read_bytes(symbols()["g_CoopSpikeBody"], 0xBC)
    return struct.unpack_from("<h", raw, 2)[0]


def run_partner(run, partner, p1, sim=True):
    """Both players' buttons, frame by frame: (partner pad names, player 1 pad names)."""
    e, mb = run.emu, mailbox(run)
    mb.set_options(OPT_PARTNER_SIM if sim else 0)
    for pp, b in zip(partner, p1):
        e.write(symbols()["g_CoopSpikePad"], sum(PAD[k] for k in pp.split("+") if k))
        run.step(1, b)


@scenario(start="entrance", disc=COOP_DISC)
def m13_spike_partner_sim(run):
    """The spike's four measurements, except the VRAM patch (drawing)."""
    e = run.emu
    start = e.save_state()
    script = ["right"] * 120 + [""] * 30 + ["cross"] * 16 + [""] * 60 + ["left"] * 90
    p1 = ["left"] * 30 + ["right"] * 30 + [""] * 256  # moves, but stays in the room (the copy is camera-relative)
    # 1. it moves as its buttons say
    run_partner(run, script[:2], p1[:2])
    x0 = body_x(e)
    run_partner(run, script[2:120], p1[2:120])
    x1 = body_x(e)
    run_partner(run, script[120:], p1[120:])
    x2 = body_x(e)
    run.expect(x1 > x0 + 40 and x2 < x1, "the partner walks right, then left, on its own buttons", x=(x0, x1, x2))
    with_sim = e.snapshot()
    with_sim_state = e.save_state()
    ram_a = e.read_bytes(0x80000000, 0x200000)
    run.step(1)
    shot_on = e.screenshot()
    cost = e.read(symbols()["g_CoopSpikeMax"])
    last = e.read(symbols()["g_CoopSpikeLines"])
    # 2. player 1 is untouched: the same run without the partner
    e.load_state(start)
    run_partner(run, script, p1, sim=False)
    alone = e.snapshot()
    run.step(1)
    shot_off = e.screenshot()
    from PIL import ImageChops
    from coop_env import TOOLS
    out = TOOLS["out"] / run.name
    out.mkdir(parents=True, exist_ok=True)
    shot_on.save(out / "partner_on.png")
    shot_off.save(out / "partner_off.png")
    box = ImageChops.difference(shot_on.convert("RGB"), shot_off.convert("RGB")).getbbox()
    run.expect(box is not None, "the partner is drawn (the screen differs only by it)", box=box)
    # its sprite is in VRAM's second bank, where player 1's is in the first (g_PlayerDraw[0].rect0)
    rx, ry, rw, rh = struct.unpack("<hhhh", e.read_bytes("g_PlayerDraw", 8))
    e.load_state(with_sim_state)
    run.step(1)
    bank = e.vram_rect(rx, 512 + ry, max(rw, 1), max(rh, 1))
    run.expect(any(any(row) for row in bank), "its sprite is in VRAM's second bank", rect=(rx, ry, rw, rh))
    same = {k: (with_sim[k], alone[k]) for k in ("world_x", "world_y", "hp", "room") if with_sim[k] != alone[k]}
    run.expect(not same, "player 1 ends the same with or without the partner", differ=same)
    # 4. determinism: the same inputs, the same RAM
    e.load_state(start)
    run_partner(run, script, p1)
    ram_b = e.read_bytes(0x80000000, 0x200000)
    differ = [i for i in range(0, 0x200000, 4) if ram_a[i:i + 4] != ram_b[i:i + 4]]
    run.expect(not differ, "the same inputs give the same 2 MB of RAM", words=len(differ), first=[hex(0x80000000 + i) for i in differ[:5]])
    # 3. the frame cost (last: the other checks still run)
    run.expect(cost < SCANLINES // 4, "the partner's frame costs under a quarter of a frame",
               scanlines=cost, percent=round(100 * cost / SCANLINES, 1), last=last)


# --- the partner's body in a two-game session ------------------------------------------------
from session import session_scenario  # noqa: E402
from session_progress import status  # noqa: E402
from link.mailbox import CHAR_ALUCARD, CHAR_RICHTER  # noqa: E402


@session_scenario(starts=("entrance", "entrance"))
def m13_partner_body_follows(run):
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


@session_scenario(starts=("entrance", "entrance"))
def m13_partner_status(run):
    """The partner's body fights as the partner: B's status (stats, level, equipment) reaches A
    and is in A's copy of B, while A's own status is untouched."""
    from link.mailbox import OPT_PARTNER_SIM, STATUS_RANGES
    a, b = run.s.a, run.s.b
    a.host("set_player", options=OPT_PARTNER_SIM)
    run.step(30)
    mine = b"".join(a.read_bytes(addr, n) for addr, n in STATUS_RANGES)
    b.write(0x80097BE8, 42)                    # g_Status.level
    b.write(0x80097BB8, 77)                    # statsBase[STR]
    b.write(0x80097C00, 0x0D)                  # equipment[0], the right hand
    run.step(60)
    theirs = b"".join(b.read_bytes(addr, n) for addr, n in STATUS_RANGES)
    # where g_Status's two ranges are in the copy (partner.c's s_Regions, in order)
    body = symbols()["g_CoopSpikeBody"]
    ofs = 64 * 0xBC + 0x3D0 + (0x80138454 - 0x80137FB4) + 0x280 + 8 + 4
    copy = a.read_bytes(body, 0x48, ofs) + a.read_bytes(body, 0x34, ofs + 0x48)
    run.expect(copy == theirs, "A's copy of B has B's status",
               differ=[i for i in range(len(theirs)) if copy[i] != theirs[i]][:8])
    now = b"".join(a.read_bytes(addr, n) for addr, n in STATUS_RANGES)
    same = [i for i in range(len(mine)) if now[i] != mine[i] and not 0 <= i < 0x18]  # hp..mpMax may tick
    run.expect(not same, "A's own status is its own", differ=same[:8])


def _swing_in_body(run, same):
    """A (Alucard) swings a hand weapon next to B, who simulates A's body. same: B holds the same
    weapon. Returns (A's animation frames, the body's, frames the body ran weapon entities,
    frames B drew A's real swing, frames B placed other partner sprites)."""
    from link.mailbox import OPT_PARTNER_SIM, WEAPON_MAGIC, WEAPON_PARTNER
    from scenarios_m12 import CATEGORY_OFS, EQUIP_DEFS, EQUIP_SIZE, N_HAND_ITEMS, WEAPON_CATEGORIES
    from scenarios_m8 import EQUIPMENT
    from session_m8 import as_characters
    from session_shared import into_hall
    a, b = run.s.a, run.s.b
    raw = a.read_bytes(EQUIP_DEFS, EQUIP_SIZE * N_HAND_ITEMS)
    items = [i for i in range(1, N_HAND_ITEMS) if raw[i * EQUIP_SIZE + CATEGORY_OFS] in WEAPON_CATEGORIES]
    a.write(EQUIPMENT, items[0], "<I")
    b.write(EQUIPMENT, items[0 if same else 1], "<I")
    as_characters(run, 0, 0)
    into_hall(run)
    for _ in range(300):
        run.step(1)
        if b.read(WEAPON_PARTNER, "<I") == WEAPON_MAGIC:
            break
    b.host("set_player", options=OPT_PARTNER_SIM)
    run.step(30)
    body = symbols()["g_CoopSpikeBody"]
    player = 0x800733D8  # g_Entities[0]
    a_frames, body_frames = set(), set()
    ran = drawn = placed = 0
    for i in range(240):
        run.step(1, ("square" if i % 40 < 2 else "", ""))
        ids = [b.read(body, "<H", k * 0xBC + 0x26) for k in range(64)]  # Entity.entityId
        ran += any(0xE0 <= x <= 0xFF for x in ids)
        a_frames.add(a.read(player + 0x56, "<h"))   # Entity.animCurFrame
        body_frames.add(b.read(body, "<h", 0x56))
        if b.read(symbols()["g_CoopWeaponsDrawn"], "<I"):
            drawn += 1
            if drawn in (2, 4):  # a frame of the swing, for the eye
                from coop_env import TOOLS
                out = TOOLS["out"] / run.name
                out.mkdir(parents=True, exist_ok=True)
                b.screenshot().save(out / f"b_swing_{drawn}.png")
                a.screenshot().save(out / f"a_swing_{drawn}.png")
        placed += bool(b.read(symbols()["g_CoopSpritesDrawn"], "<I"))
    return a_frames, body_frames, ran, drawn, placed


@session_scenario()
def m13_partner_weapon_differs(run):
    """A's weapon isn't B's: B's copy of A strikes A's poses (its own weapon entity can't run: the
    overlay is B's weapon's, and drops it), and B draws A's real swing from the link, where the
    body is; no other partner sprites on top of the body."""
    a_frames, body_frames, ran, drawn, placed = _swing_in_body(run, same=False)
    run.expect(len(a_frames) > 4 and a_frames <= body_frames, "B's copy of A strikes A's poses",
               missing=sorted(a_frames - body_frames))
    run.expect(drawn, "B draws A's real swing", frames=drawn)
    run.expect(not placed, "and no partner sprites over the body", frames=placed)


@session_scenario()
def m13_partner_weapon_same(run):
    """The same weapon: B's copy of A swings it and draws it itself; nothing comes from the link."""
    a_frames, body_frames, ran, drawn, placed = _swing_in_body(run, same=True)
    run.expect(ran and a_frames <= body_frames, "B's copy of A swings", frames=ran,
               missing=sorted(a_frames - body_frames))
    run.expect(not drawn and not placed, "drawn by the body alone", real=drawn, sprites=placed)


@session_scenario(starts=("entrance", "entrance"), characters=(CHAR_ALUCARD, CHAR_RICHTER))
def m13_partner_richter(run):
    """M13 step 3: B plays Richter, and A (Alucard) runs B's body with our partner Richter (its
    own code and statics: COOPRICP.BIN), from B's buttons: the body is Richter's (his animation
    set), moves and animates as B does, and draws from Richter's graphics in VRAM's second bank.
    A's own game is untouched: its character, its sprite banks, its player."""
    from link.mailbox import OPT_PARTNER_SIM
    from session_m8 import reload_game
    a, b = run.s.a, run.s.b
    run.expect(reload_game(run, b) and b.mailbox("self_presence").character == CHAR_RICHTER, "B plays Richter")
    run.step(60)
    sym = symbols()
    banks_at = a.read("g_api", "<I", 0x10)  # g_api.o.spriteBanks (Overlay: +0x10)
    banks = a.read_bytes(banks_at + 0x40, 16)
    a.host("set_player", options=OPT_PARTNER_SIM)
    run.step(30)
    body = sym["g_CoopSpikeBody"]
    run.expect(a.read(body, "<h", 0x54) == -0x7FF0, "A's copy of B is Richter (his animation set, 0x8010)",
               anim_set=hex(a.read(body, "<H", 0x54)))
    poses, worst, samples = set(), 0, 0
    pattern = ["right"] * 60 + ["right+cross"] * 14 + ["right"] * 40 + ["left"] * 80 + ["left+square"] * 20 + [""] * 40
    for t, pad in enumerate(pattern):
        run.step(1, ("", pad))
        poses.add(a.read(body, "<H", 0x56))  # animCurFrame
        if t % 10 == 0:
            bx = a.read(body, "<h", 2) + a.read("g_Tilemap", "<h", 0x0A)
            sb = b.snapshot()
            if sb["room"] == a.snapshot()["room"]:
                worst = max(worst, abs(bx - sb["world_x"]))
                samples += 1
        if t in (160, 200, 206):  # for eyes: .env/out/shots/
            shots = Path(__file__).resolve().parent.parent / ".env/out/shots"
            shots.mkdir(parents=True, exist_ok=True)
            a.screenshot().save(shots / f"m13_partner_richter_{t}.png")
    run.expect(samples > 10 and worst <= 48, "A's copy follows B (within the snap distance)", worst_px=worst, samples=samples)
    run.expect(len(poses) > 8, "and animates as B moves, jumps and whips", poses=len(poses))
    # FGAME2_ADDR's strip 4 (32 x 128 at 0x240, 0x100: strips 0-3 hold the player sprites' frames)
    fgame2 = a.read_bytes(0x80680000 + 4 * 0x2000, 0x2000)
    strip = b"".join(struct.pack("<32H", *row) for row in a.vram_rect(0x240, 0x100 + 512, 32, 128))
    run.expect(strip == fgame2, "Richter's graphics are in A's second bank")
    run.expect(a.read(0x80280020) == 0, "A's player is still Alucard (g_CoopCharacter)")
    run.expect(a.read_bytes(banks_at + 0x40, 16) == banks, "A's sprite banks 16-19 are its own")
    run.expect(a.snapshot()["hp"] > 0 and a.read("g_Entities", "<h", 0x54) != -0x7FF0, "A plays on as Alucard")


@session_scenario(starts=("entrance", "entrance"), characters=(CHAR_ALUCARD, 2))
def m13_partner_maria(run):
    """M13 step 3: B plays Maria, and A (Alucard) runs B's body with our partner Maria (her own
    build, MARIAP.BIN, from her blob): it's Maria's body (B's animation set), it follows and
    animates as B does, and A's own game is untouched."""
    from link.mailbox import CHAR_MARIA, OPT_PARTNER_SIM
    from session_m8 import reload_game
    a, b = run.s.a, run.s.b
    run.expect(reload_game(run, b) and b.mailbox("self_presence").character == CHAR_MARIA, "B plays Maria")
    run.step(60)
    banks_at = a.read("g_api", "<I", 0x10)
    banks = a.read_bytes(banks_at + 0x40, 16)
    a.host("set_player", options=OPT_PARTNER_SIM)
    run.step(30)
    body = symbols()["g_CoopSpikeBody"]
    run.expect(a.read(body, "<h", 0x54) == b.read("g_Entities", "<h", 0x54),
               "A's copy of B is Maria (B's animation set)", a=hex(a.read(body, "<H", 0x54)), b=hex(b.read("g_Entities", "<H", 0x54)))
    poses, worst, samples = set(), 0, 0
    pattern = ["right"] * 60 + ["right+cross"] * 14 + ["right"] * 40 + ["left"] * 80 + ["left+square"] * 20 + [""] * 40
    shots = Path(__file__).resolve().parent.parent / ".env/out/shots"
    shots.mkdir(parents=True, exist_ok=True)
    for t, pad in enumerate(pattern):
        run.step(1, ("", pad))
        poses.add(a.read(body, "<H", 0x56))
        if t % 10 == 0:
            bx = a.read(body, "<h", 2) + a.read("g_Tilemap", "<h", 0x0A)
            sb = b.snapshot()
            if sb["room"] == a.snapshot()["room"]:
                worst = max(worst, abs(bx - sb["world_x"]))
                samples += 1
        if t in (160, 200, 206):
            a.screenshot().save(shots / f"m13_partner_maria_{t}.png")
            b.screenshot().save(shots / f"m13_partner_maria_{t}_b.png")
    run.expect(samples > 10 and worst <= 48, "A's copy follows B (within the snap distance)", worst_px=worst, samples=samples)
    run.expect(len(poses) > 8, "and animates as B moves, jumps and attacks", poses=len(poses))
    run.expect(a.read(0x80280020) == 0, "A's player is still Alucard (g_CoopCharacter)")
    run.expect(a.read_bytes(banks_at + 0x40, 16) == banks, "A's sprite banks 16-19 are its own")
    run.expect(a.snapshot()["hp"] > 0 and a.read("g_Entities", "<h", 0x54) != b.read("g_Entities", "<h", 0x54), "A plays on as Alucard")


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


@session_scenario(starts=("entrance", "entrance"), characters=(CHAR_RICHTER, CHAR_RICHTER))
def m13_partner_rr(run):
    """M13 step 3: Richter's game, a Richter partner (a second Richter, statics of his own)."""
    _partner_pair(run, CHAR_RICHTER, CHAR_RICHTER)


@session_scenario(starts=("entrance", "entrance"), characters=(CHAR_RICHTER, 2))
def m13_partner_rm(run):
    """M13 step 3: Richter's game, a Maria partner."""
    _partner_pair(run, CHAR_RICHTER, 2)


@session_scenario(starts=("entrance", "entrance"), characters=(2, CHAR_RICHTER))
def m13_partner_mr(run):
    """M13 step 3: Maria's game, a Richter partner."""
    _partner_pair(run, 2, CHAR_RICHTER)


@session_scenario(starts=("entrance", "entrance"), characters=(2, 2))
def m13_partner_mm(run):
    """M13 step 3: Maria's game, a Maria partner (a second Maria)."""
    _partner_pair(run, 2, 2)


@session_scenario(starts=("entrance", "entrance"), characters=(CHAR_RICHTER, CHAR_ALUCARD))
def m13_partner_ra(run):
    """M13 step 3c: Richter's game, an Alucard partner (DRA's Alucard, ARC_F's tables swapped in,
    his graphics in the second bank, none of his palette operations kept)."""
    _partner_pair(run, CHAR_RICHTER, CHAR_ALUCARD)


@session_scenario(starts=("entrance", "entrance"), characters=(2, CHAR_ALUCARD))
def m13_partner_ma(run):
    """M13 step 3c: Maria's game, an Alucard partner."""
    _partner_pair(run, 2, CHAR_ALUCARD)


FAMILIAR_CARDS = {"bat": 0x12, "ghost": 0x13, "faerie": 0x14, "demon": 0x15, "sword": 0x16}  # g_Status.relics


@session_scenario(starts=("entrance", "entrance"))
def m13_partner_familiar(run):
    """M13 step 4 (criterion 3): the partner's familiar shows and follows them. B switches each
    card on in turn (its game loads the familiar); A, running B's body, draws B's familiar from
    B's copy (overlay, sheet, palettes: module/familiar.c) in its second bank, beside the body."""
    from link.mailbox import OPT_PARTNER_SIM
    from session_m8 import reload_game
    a, b = run.s.a, run.s.b
    sym = symbols()
    a.host("set_player", options=OPT_PARTNER_SIM)
    shots = Path(__file__).resolve().parent.parent / ".env/out/shots"
    shots.mkdir(parents=True, exist_ok=True)
    for name, card in FAMILIAR_CARDS.items():
        for c in FAMILIAR_CARDS.values():
            b.write(0x80097964 + c, 3 if c == card else 1, "<B")  # found; only this one on
        run.expect(reload_game(run, b), f"B reloads with the {name} card on")
        drawn = 0
        for t in range(240):
            run.step(1, ("", "right" if t % 120 < 40 else ""))
            drawn = max(drawn, a.read(sym["g_CoopFamiliarDrawn"]))
        a.screenshot().save(shots / f"m13_partner_familiar_{name}.png")
        ok = drawn > 0  # sprites, or primitives (the sword)
        run.expect(ok, f"A draws B's {name}", drawn=drawn, servant=b.read("g_ServantLoaded"))
        sheet = b"".join(struct.pack("<64H", *r) for r in b.vram_rect(0x2C0, 0x100, 64, 128))
        mine = b"".join(struct.pack("<64H", *r) for r in a.vram_rect(0x2C0, 0x100 + 512, 64, 128))
        run.expect(sheet == mine, f"with B's {name} graphics, in A's second bank")


@session_scenario(starts=("entrance", "entrance"), characters=(CHAR_ALUCARD, CHAR_RICHTER))
def m13_partner_sounds(run):
    """M13 step 4 (risks: two players' sounds): A stands still while B's Richter jumps and whips.
    Every sound request in A's ring from then on is the partner's: at most 60% of its volume, and
    none from the player's voice bank (Richter's voice isn't in Alucard's game)."""
    from link.mailbox import OPT_PARTNER_SIM
    from session_m8 import reload_game
    a, b = run.s.a, run.s.b
    run.expect(reload_game(run, b), "B plays Richter")
    run.step(60)
    a.host("set_player", options=OPT_PARTNER_SIM)
    run.step(30)
    ring, wpos, sfx = 0x801390DC, 0x80139000, 0x800BF554  # g_SfxRingBuffer, its write pos, g_SfxData
    pos, seen, loud, voice = a.read(wpos, "<h"), 0, [], 0
    for t, pad in enumerate((["right+cross"] * 14 + ["square"] * 20 + [""] * 26) * 4):
        run.step(1, ("", pad))
        while pos != a.read(wpos, "<h"):
            sid, vol, pan = struct.unpack("<hHh", a.read_bytes(ring + 6 * pos, 6))
            seen += 1
            if a.read(sfx + 7 * sid, "<B") == 1:  # vabid: the player's bank
                voice += vol != 0
            elif vol == 0xFFFF or vol > 0x7F * 60 // 100:
                loud.append((sid, vol))
            pos = (pos + 1) & 0xFF
    run.expect(seen > 0, "the partner's whip and jumps make sounds in A's game", sounds=seen)
    run.expect(not loud, "all at 60% of their volume or less", loud=loud[:6])
    run.expect(voice == 0, "none from the player's voice bank", voice=voice)


HALL_SPOT = (0x41, 72, 1331, 199)  # the entrance hall (stage, room, x, y), where die() finds zombies


def _respawn_effect(run, ca):
    """A (playing ca) dies in the entrance hall and is revived at B (in the Alchemy Lab): A's own
    game plays A's character's teleport-in (its player init, as after a teleporter), A's presence
    says so, and B's copy of A is made with it too (criterion 6: m13_respawn_effect_*)."""
    from link.mailbox import FLIP_TELEPORT_IN, OPT_PARTNER_SIM
    from session_m8 import reload_game
    from session_travel import die
    a, b = run.s.a, run.s.b
    sym = symbols()
    if ca != CHAR_ALUCARD:
        run.expect(reload_game(run, a) and a.mailbox("self_presence").character == ca, f"A plays {ca}")
    b.host("set_player", options=OPT_PARTNER_SIM)
    run.step(300)
    if ca != CHAR_ALUCARD:  # a reload puts them in the first room's middle: to the hall's zombies
        from session_progress import arrive
        arrive(run, a, *HALL_SPOT)
    ins0, bodies0 = a.read(sym["g_CoopTeleportIns"]), b.read(sym["g_CoopBodyTeleports"])
    run.expect(die(run, a) is not None, "A died")
    flagged = False
    for i in range(1200):
        run.step(1)
        flagged |= bool(a.mailbox("self_presence").flip_x & FLIP_TELEPORT_IN)
        if b.read(sym["g_CoopBodyTeleports"]) > bodies0 and i > 30:
            break
    shots = Path(__file__).resolve().parent.parent / ".env/out/shots"
    shots.mkdir(parents=True, exist_ok=True)
    run.step(20)
    a.screenshot().save(shots / f"m13_respawn_{ca}_a.png")
    b.screenshot().save(shots / f"m13_respawn_{ca}_b.png")
    run.expect(a.read(sym["g_CoopTeleportIns"]) > ins0, "A came in with its teleport-in")
    run.expect(flagged, "A's presence said so")
    run.expect(b.read(sym["g_CoopBodyTeleports"]) > bodies0, "B's copy of A came in with it too")
    img = b.screenshot().convert("L").resize((64, 48))
    white = sum(1 for v in img.getdata() if v > 230) / (64 * 48)
    run.expect(white < 0.5, "and its white flash isn't on B's screen (that's B's player's)", white=round(white, 2))
    run.expect(a.snapshot()["hp"] > 0 and b.snapshot()["hp"] > 0, "both play on")


@session_scenario(starts=("entrance", "nz0"))
def m13_respawn_effect_alucard(run):
    _respawn_effect(run, CHAR_ALUCARD)


@session_scenario(starts=("entrance", "nz0"), characters=(CHAR_RICHTER, CHAR_ALUCARD))
def m13_respawn_effect_richter(run):
    _respawn_effect(run, CHAR_RICHTER)


@session_scenario(starts=("entrance", "nz0"), characters=(2, CHAR_ALUCARD))
def m13_respawn_effect_maria(run):
    _respawn_effect(run, 2)


LIFE_APPLE = 0x26 + 0x92  # g_Status.equipHandCount[ITEM_LIFE_APPLE], from g_Status


@session_scenario(starts=("entrance", "entrance"))
def m13_fairy_revive(run):
    """M13 criterion 6: B (Alucard) has the faerie out and a Life Apple is in the shared bag; A
    dies in B's room (the hall: A is its authority, the zombies are A's) and is revived where it
    fell, not at B; the apple is gone in both games."""
    from link.mailbox import OPT_PARTNER_SIM
    from session_m8 import reload_game
    from session_shared import into_hall
    from session_travel import die
    a, b = run.s.a, run.s.b
    b.write(0x80097964 + 0x14, 3, "<B")  # the faerie card, on
    run.expect(reload_game(run, b), "B reloads with the faerie card on")
    for g in (a, b):
        g.write("g_Status", 1, "<B", LIFE_APPLE)
    a.host("set_player", options=OPT_PARTNER_SIM)
    b.host("set_player", options=OPT_PARTNER_SIM)
    into_hall(run)
    run.step(60)
    run.expect(a.read(0x807E0008) == 3, "A knows B's familiar is the faerie (B's copy of it)", servant=a.read(0x807E0008))
    room = a.mailbox("self_presence").room
    run.expect(die(run, a) is not None, "A died")
    x0 = a.snapshot()["world_x"]
    for i in range(900):  # the death animation, then the revive (respawn_at_partner's wait)
        run.step(1)
        p = a.mailbox("self_presence")
        if p.flags & 1 and not p.flags & (8 | 16) and status(a)["hp"] == status(a)["hp_max"]:
            break
    run.step(30)
    p = a.mailbox("self_presence")
    run.expect(p.room == room and abs(a.snapshot()["world_x"] - x0) < 48, "A is revived where it fell",
               room=str(p.room), was=str(room), x=a.snapshot()["world_x"], x0=x0)
    run.expect(status(a)["hp"] == status(a)["hp_max"], "with full HP", hp=status(a)["hp"])
    run.expect(a.read("g_Status", "<B", LIFE_APPLE) == 0 and b.read("g_Status", "<B", LIFE_APPLE) == 0,
               "the Life Apple is gone in both games", a=a.read("g_Status", "<B", LIFE_APPLE), b=b.read("g_Status", "<B", LIFE_APPLE))
