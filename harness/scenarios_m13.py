"""M13 spike (design/M13-partner-player.md): the partner simulated by the game's own player code,
in one game, driven by scripted buttons (module/partner.c, OPT_PARTNER_SIM). Measures what the
spike must answer: the partner moves as its buttons say, player 1 is untouched, the frame cost,
and determinism."""

import struct
from pathlib import Path

from module import COOP_DISC, symbols
from scenario import scenario

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




@scenario(start="entrance", disc=COOP_DISC)
def partner_vram_banks_draw(run):
    """M17 step 1 (design/M17-more-players.md): the core's four VRAM banks. One of the HUD's sprites is
    pointed at bank 1, 2 and 3 in turn, through its texpage (bits 14-15) and then its palette (CLUT
    bit 15, x bits 4-5), with each bank holding something the first doesn't: it draws from that
    bank. Bank 1's encoding is the two-player one, unchanged."""
    import libretro
    e = run.emu
    run.step(30)
    mem = e._session.core.get_memory(libretro.RETRO_MEMORY_VIDEO_RAM)
    run.expect(len(mem) == 1024 * 2048 * 2, "VRAM holds four banks", size=len(mem))
    if len(mem) != 1024 * 2048 * 2:
        return
    buf = e.addr("g_PrimBuf")
    p = buf + e.read(0x80137970, "<i") * 0x34  # g_PlayerHud.primIndex1: the HUD's sprites
    while p and (e.read_bytes(p + 7, 1)[0] != 4 or e.read(p, "<H", 0x32) & 8):  # a GT4, not hidden
        p = e.read(p)
    tpage, clut = e.read(p, "<H", 0x1A), e.read(p, "<H", 0x0E)
    x0, y0, x3, y3 = (e.read(p, "<h", o) for o in (0x08, 0x0A, 0x2C, 0x2E))
    run.expect(p and not tpage & 0xC000 and not clut & 0x8000,
               "a HUD sprite: a GT4 in bank 0, drawn", tpage=hex(tpage), clut=hex(clut))
    page_x, page_y = (tpage & 0xF) * 64, (tpage >> 4 & 1) * 256
    pal_x, pal_y = 0, 0xF0  # where banked palettes are (partner.c BankClut): the test's own row
    base = bytes(mem[:1024 * 512 * 2])

    def bank(b, texture=None, palette=None):  # bank b: a copy of bank 0, its page or palette changed
        img = bytearray(base)
        if texture is not None:
            for row in range(page_y, page_y + 256):
                img[(row * 1024 + page_x) * 2:(row * 1024 + page_x + 64) * 2] = struct.pack("<H", texture) * 64
        if palette is not None:
            o = (pal_y * 1024 + pal_x) * 2
            img[o + 2:o + 32] = struct.pack("<H", palette) * 15  # every colour but 0 (see-through)
        mem[b * 1024 * 512 * 2:(b + 1) * 1024 * 512 * 2] = img

    def drawn():
        shot = e.screenshot()
        return {shot.getpixel((x, y)) for x in range(max(x0, 0), min(x3, 255)) for y in range(max(y0, 0), min(y3, 239))}

    plain = drawn()
    for b in (1, 2, 3):  # textures: the page is all colour b in bank b
        bank(b, texture=0x1111 * b)
    seen = {}
    for b in (1, 2, 3):
        e.write(p, (tpage & ~0xC000) | b << 14, "<H", 0x1A)
        run.step(3)  # the frame after next is drawn from it
        seen[b] = drawn()
        e.write(p, tpage, "<H", 0x1A)
    for b in (1, 2, 3):  # the HUD around it draws over part of its box: compare the banks' results
        others = [seen[k] for k in (1, 2, 3) if k != b] + [plain]
        run.expect(all(seen[b] != o for o in others), f"texpage bank {b}: drawn from bank {b}'s page",
                   colours=len(seen[b]))
    run.step(3)
    plain = drawn()
    colours = {1: 0x801F, 2: 0x83E0, 3: 0xFC00}  # red, green, blue
    for b, c in colours.items():
        bank(b, palette=c)
    ids = e.addr("g_ClutIds") + 2 * (clut & 0x3FF)  # a primitive's clut is an index into these
    original = e.read(ids, "<H")
    for b, c in colours.items():
        e.write(ids, 0x8000 | pal_y << 6 | (b - 1) << 4 | pal_x // 16, "<H")
        run.step(3)
        seen = drawn() - plain
        e.write(ids, original, "<H")
        want = ((c & 0x1F) * 255 // 31, (c >> 5 & 0x1F) * 255 // 31, (c >> 10 & 0x1F) * 255 // 31)
        run.expect(any(max(abs(a - w) for a, w in zip(s, want)) <= 8 for s in seen),
                   f"palette bank {b}: drawn in bank {b}'s colour", want=want, seen=sorted(seen)[:4])


@session_scenario(characters=(0, 1))
def partner_sounds_alucard_and_richter(run):
    """#344 (playtest 1.3.0: Richter couldn't be heard): Richter's own sounds (his bank, VAB 1) aren't
    in Alucard's game's sound memory, which holds Alucard's. A hands them to its host, which plays
    them from Richter's bank on the disc: each one A hands over is one the host can play."""
    from session_m8 import reload_game
    from session_shared import into_hall
    a, b = run.s.a, run.s.b
    run.expect(reload_game(run, b) and b.mailbox("self_presence").character == CHAR_RICHTER, "B plays Richter")
    into_hall(run)
    before = a.voices("check")[0]
    for _ in range(8):  # Richter whips (□), and jumps
        run.step(4, ("", "square"))
        run.step(30, ("", ""))
        run.step(6, ("", "cross"))
        run.step(20, ("", ""))
    played, kinds, rendered = a.voices("check")
    sym = symbols()
    run.expect(played - before >= 4, "A hands Richter's own sounds to its host", sounds=played - before, kinds=kinds,
               out=a.read(sym["g_CoopSoundsOut"]), bodies=a.read(sym["g_CoopBodiesMade"]),
               b_char=b.mailbox("self_presence").character, rooms=(a.snapshot()["room"], b.snapshot()["room"]))
    run.expect(rendered == kinds, "the host plays every one of them from Richter's bank", kinds=kinds, rendered=rendered)
    peak = a.voices("mix_check")
    run.expect(peak > 1000, "mixed into A's sound, they're heard", peak=peak)
