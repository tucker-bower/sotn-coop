"""Other mods' characters (docs/design/character-mods.md): Ultimate Maria, SOTN Ultimate's PSP
Maria, in Alucard's castle. One game on the co-op disc; she needs the dev DXC disc, as Co-op
Maria does."""

import struct

from bots import walker
from link.mailbox import CHAR_ALUCARD
from module import COOP_DISC, maria_blob
from scenario import scenario
from session import session_scenario
from scenarios_m8 import RICHTER_OVERLAY, mailbox, reload_as

BLOB_HEAD = 0x20  # module/link.h CharBlob


def blobs():
    """{CHAR_*: (offset of its overlay in maria_blob(), its CharBlob fields)}."""
    b, out, at = maria_blob(), {}, 0
    while at + BLOB_HEAD <= len(b) and struct.unpack_from("<I", b, at)[0] == 0x52414843:
        magic, ch, ovl, vh, vb, partner, vh2, vb2 = struct.unpack_from("<8I", b, at)
        out[ch] = (at + BLOB_HEAD, (ovl, vh, vb, partner, vh2, vb2))
        at += BLOB_HEAD + sum((n + 3) & ~3 for n in (ovl, vh, vb, partner, vh2, vb2))
    return out


SUBWEAPON, FRONT = 0x80097BFC, 0x80097C40  # g_Status.subWeapon (the other slot), D_80097C40 (hers)
DAGGER, AXE, BIBLE = 1, 2, 5               # include/game.h SubWpnID
HUD_PRIM_INDEX1, PRIM_BUF, PRIM_SIZE = 0x80137970, 0x80086FEC, 0x34  # g_PlayerHud.primIndex1, g_PrimBuf
DRAW_HIDE, PRIM_GT4 = 8, 4


@scenario(start="entrance", disc=COOP_DISC)
def saturn_maria_in_the_castle(run):
    """Saturn Maria (SOTN Ultimate's): an Alucard save loads as her, her overlay (made from the
    Saturn disc, as the launcher makes it) in Richter's slot and her code in the 8MB, she walks
    and attacks, and loads back as Alucard."""
    from link.mailbox import CHAR_SAT_MARIA
    from coop_env import TOOLS
    e, mb = run.emu, mailbox(run)
    found = blobs()
    run.expect(CHAR_SAT_MARIA in found, "her blob is made (the dev Saturn disc: LOCAL.md)", has=sorted(found))
    reload_as(run, mb, CHAR_SAT_MARIA)
    run.expect(mb.self_presence().character == CHAR_SAT_MARIA, "the game reports Saturn Maria",
               character=mb.self_presence().character)
    # her player table (g_PlOvl); the frame table after it is hers to rewrite: she unpacks her
    # LZSS images into buffers every frame and points it at them
    at = found[CHAR_SAT_MARIA][0]
    run.expect(e.read_bytes(RICHTER_OVERLAY, 32) == maria_blob()[at:at + 32], "Richter's slot holds her overlay")
    s0 = e.snapshot()
    s = run.play(walker("left", attack_every=12), 300)
    e.screenshot().save(TOOLS["out"] / "saturn_maria_in_the_castle" / "walk.png")
    run.expect((s["world_x"] < s0["world_x"] - 50 or s["room"] != s0["room"]) and s["hp"] > 0,
               "she walks and attacks in the castle", moved=s0["world_x"] - s["world_x"], room=s["room"])
    reload_as(run, mb, CHAR_ALUCARD)
    run.expect(mb.self_presence().character == CHAR_ALUCARD, "and loads back as Alucard")


@session_scenario(starts=("entrance", "entrance"), characters=(CHAR_ALUCARD, 4))
def partner_body_alucard_and_saturn_maria(run):
    """Alucard's game, a Saturn Maria partner: her partner build (PARTNER_SAT_ADDR), its sprite
    table taken again each frame as her code unpacks her images."""
    from scenarios_m13 import _partner_pair
    _partner_pair(run, CHAR_ALUCARD, 4)


MP, MP_MAX = 0x80097BB0, 0x80097BB4  # g_Status
ENGINE_STEP, HALT = 0x8003C9A4, 0x80097420  # g_GameEngineStep, g_unkGraphicsStruct.unk28
ENGINE_HALT, HALT_BEASTS = 5, 4


def facing_left(e):
    return e.read("g_Entities", "<H", 0x14) != 0  # PLAYER.facingLeft


def rise_of(run, inputs):
    """How high (px) she gets above where she stood while the inputs play, then lands."""
    e = run.emu
    y0, best = e.snapshot()["world_y"], 0
    for b in inputs:
        run.step(1, b)
        best = max(best, y0 - e.snapshot()["world_y"])
    run.step(60)
    return best


@scenario(start="entrance", disc=COOP_DISC)
def saturn_maria_moves(run):
    """Saturn Maria plays as SOTN Ultimate built her: R1 is her backdash (a hop away from where
    she faces), and she has a double jump of her own, with no relic (Co-op Maria's needs the Leap
    Stone, whatever the castle's rules: these are hers)."""
    from link.mailbox import CHAR_SAT_MARIA
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, CHAR_SAT_MARIA)
    run.step(120)  # the load's landing: she crouches a moment
    left, x0 = facing_left(e), e.snapshot()["world_x"]
    run.step(2, "r1")
    run.step(40)
    moved = e.snapshot()["world_x"] - x0
    run.expect(abs(moved) > 12 and (moved > 0) == left, "R1: a backdash, away from where she faces",
               moved=moved, facing_left=left)
    single = rise_of(run, ["cross"] * 12 + [""] * 40)
    double = rise_of(run, ["cross"] * 10 + [""] * 6 + ["cross"] * 10 + [""] * 40)
    run.expect(double > single + 10, "a second jump in the air takes her higher", single=single, double=double)


@scenario(start="entrance", disc=COOP_DISC)
def saturn_maria_beasts(run):
    """Byakko (Up, Down, Down-forward, Forward, Square; 100 MP) halts the game while the beast
    strikes, and her own code ends the halt: our DRA runs only the stage in a halt for anyone but
    Alucard, so the module runs her there (character.c SaturnMariaHalt). Without it, the game
    stayed frozen."""
    from link.mailbox import CHAR_SAT_MARIA
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, CHAR_SAT_MARIA)
    run.step(120)
    e.write(MP_MAX, 200)
    e.write(MP, 200)
    fwd = "left" if facing_left(e) else "right"
    for pad in ("up", "down", f"down+{fwd}", fwd):
        run.step(4, pad)
    run.step(2, f"{fwd}+square")
    halted = ended = False
    for i in range(900):
        run.step(1)
        if e.read(ENGINE_STEP) == ENGINE_HALT and e.read(HALT, "<i") == HALT_BEASTS:
            halted = True
        elif halted and e.read(ENGINE_STEP) != ENGINE_HALT:
            ended = True
            break
    run.expect(halted, "Byakko halts the game (the beast strikes)", mp=e.read(MP))
    run.expect(ended, "and her code ends the halt", frames=i, step=e.read(ENGINE_STEP), halt=e.read(HALT, "<i"))
    run.expect(e.read(MP) < 140, "it cost her 100 MP (she gets some back as it plays)", mp=e.read(MP))
    s0 = e.snapshot()
    s = run.play(walker("left", attack_every=12), 120)
    run.expect(s["world_x"] != s0["world_x"] or s["room"] != s0["room"], "and she plays on")


SFX_DATA = 0x800BF554  # g_SfxData: 7 bytes a sound from id 0x600 (vabid, prog, note, volume, mode, tone, prio)


def sfx(e, sid):
    return e.read_bytes(SFX_DATA + (sid - 0x600) * 7, 7)


RIC_SHEET = 0x8013C020  # richter_sprites
RIC2_HDR = 0x170AC - 8  # in his file: {magic "RIC2", the block's address}


def coat_palettes(blob_file):
    """[(palette id, 16 colours)] of his coat's block (launcher/saturn_richter.py)."""
    magic, ptr = struct.unpack_from("<II", blob_file, RIC2_HDR)
    assert magic == 0x32434952
    o = ptr - RICHTER_OVERLAY
    n = struct.unpack_from("<I", blob_file, o)[0]
    o += 4
    out = []
    for _ in range(n):  # {palette id: u32, 16 colours}
        out.append((struct.unpack_from("<I", blob_file, o)[0], list(struct.unpack_from("<16H", blob_file, o + 4))))
        o += 4 + 32
    return out


@scenario(start="entrance", disc=COOP_DISC)
def ultimate_richter_in_the_castle(run):
    """Ultimate Richter (SOTN Ultimate's, D184): retail Richter's code with the Saturn's coat, made
    from the player's discs. After his load, Richter's slot has the coat's sprite sheet, and the
    game's palettes (RAM copy and VRAM) his coat's colours; he walks and attacks; back as
    Alucard."""
    from coop_env import TOOLS
    e, mb = run.emu, mailbox(run)
    found = blobs()
    run.expect(5 in found, "his blob is made (the dev Saturn disc: LOCAL.md)", has=sorted(found))
    at, (size, *_) = found[5]
    coat = maria_blob()[at:at + size]
    reload_as(run, mb, 5)
    run.step(60)
    run.expect(mb.self_presence().character == 5, "the game reports Ultimate Richter")
    run.expect(e.read_bytes(RIC_SHEET, 0x314) == coat[0x20:0x20 + 0x314], "Richter's slot has the coat's sheet")
    pals = coat_palettes(coat)
    clut = e.addr("g_Clut")
    got = [list(struct.unpack_from("<16H", e.read_bytes(clut + 0x2000 + (pid - 0x100) * 32, 32))) for pid, _ in pals]
    vram = [list(e.vram_rect(((pid - 0x100) % 16) * 16, 0xF0 + (pid - 0x100) // 16, 16, 1)[0]) for pid, _ in pals]
    run.expect(pals and vram == [q for _, q in pals], "VRAM's palettes have his coat's colours", palettes=len(pals),
               first=[hex(v) for v in vram[0][:4]] if vram else None, want=[hex(v) for v in pals[0][1][:4]] if pals else None)
    run.expect(pals and got == [q for _, q in pals], "the game's palettes (RAM) have his coat's colours", palettes=len(pals),
               first=[hex(v) for v in got[0][:4]] if got else None)
    s0 = e.snapshot()
    s = run.play(walker("left", attack_every=12), 300)
    e.screenshot().save(TOOLS["out"] / "ultimate_richter_in_the_castle" / "coat.png")
    run.expect((s["world_x"] < s0["world_x"] - 50 or s["room"] != s0["room"]) and s["hp"] > 0,
               "he walks and attacks in the castle", moved=s0["world_x"] - s["world_x"])
    reload_as(run, mb, CHAR_ALUCARD)
    run.expect(mb.self_presence().character == CHAR_ALUCARD, "and loads back as Alucard")


