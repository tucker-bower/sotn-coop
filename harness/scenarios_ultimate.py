"""Other mods' characters (docs/design/character-mods.md): Ultimate Maria, SOTN Ultimate's PSP
Maria, in Alucard's castle. One game on the co-op disc; she needs the dev DXC disc, as Co-op
Maria does."""

import struct

from bots import walker
from link.mailbox import CHAR_ALUCARD, CHAR_MARIA, CHAR_ULT_MARIA
from module import COOP_DISC, maria_blob
from scenario import scenario
from session import session_scenario
from scenarios_m8 import RICHTER_OVERLAY, mailbox, reload_as

BLOB_HEAD = 0x20  # module/link.h CharBlob


def blobs():
    """{CHAR_*: (offset of its overlay in maria_blob(), its CharBlob fields)}."""
    b, out, at = maria_blob(), {}, 0
    while at + BLOB_HEAD <= len(b) and struct.unpack_from("<I", b, at)[0] == 0x52414843:
        magic, ch, ovl, vh, vb, partner, _, _ = struct.unpack_from("<8I", b, at)
        out[ch] = (at + BLOB_HEAD, (ovl, vh, vb, partner))
        at += BLOB_HEAD + sum((n + 3) & ~3 for n in (ovl, vh, vb, partner))
    return out


@scenario(start="entrance", disc=COOP_DISC)
def ultimate_maria_in_the_castle(run):
    """An Alucard save loads as Ultimate Maria: her own overlay in Richter's slot (the blob's
    second part, not Co-op Maria's), the world stays Alucard's, she walks and attacks, and the
    game loads back as Alucard."""
    e, mb = run.emu, mailbox(run)
    found = blobs()
    run.expect(CHAR_MARIA in found and CHAR_ULT_MARIA in found, "the blob holds both Marias", has=sorted(found))
    reload_as(run, mb, CHAR_ULT_MARIA)
    run.expect(mb.self_presence().character == CHAR_ULT_MARIA, "the game reports Ultimate Maria",
               character=mb.self_presence().character)
    at = found[CHAR_ULT_MARIA][0]
    run.expect(e.read_bytes(RICHTER_OVERLAY, 64) == maria_blob()[at:at + 64], "Richter's slot holds her overlay")
    run.expect(e.read("g_PlayableCharacter") == 0, "the world still sees Alucard")
    s0 = e.snapshot()
    s = run.play(walker("left", attack_every=12), 300)
    run.expect((s["world_x"] < s0["world_x"] - 50 or s["room"] != s0["room"]) and s["hp"] > 0,
               "she walks and attacks in the castle", moved=s0["world_x"] - s["world_x"], room=s["room"])
    reload_as(run, mb, CHAR_ALUCARD)
    run.expect(mb.self_presence().character == CHAR_ALUCARD, "and loads back as Alucard")


SUBWEAPON, FRONT = 0x80097BFC, 0x80097C40  # g_Status.subWeapon (the other slot), D_80097C40 (hers)
DAGGER, AXE, BIBLE = 1, 2, 5               # include/game.h SubWpnID
HUD_PRIM_INDEX1, PRIM_BUF, PRIM_SIZE = 0x80137970, 0x80086FEC, 0x34  # g_PlayerHud.primIndex1, g_PrimBuf
DRAW_HIDE, PRIM_GT4 = 8, 4
# her HUD icons' texture corner (u, v) by Richter id (mar2.c g_Mar2HudIconDefs)
ICON_UV = {DAGGER: (0xE0, 0xB0), AXE: (0xD0, 0xC0), BIBLE: (0x98, 0xD8)}


def ult_symbol(name):
    """An address in her build (nm of ultmar.elf): her statics aren't in the game's symbols."""
    import subprocess
    from coop_env import REPO
    out = subprocess.run(["mipsel-linux-gnu-nm", str(REPO / "build/coop/maria-ultimate/ultmar.elf")],
                         capture_output=True, text=True, check=True).stdout
    return next(int(a, 16) for a, _, n in (line.split() for line in out.splitlines() if len(line.split()) == 3)
                if n == name)


def hud_icons(e):
    """((u, v) of DRA's HUD icon sprite, (u, v, shown) of her own one behind it)."""
    i = e.read(HUD_PRIM_INDEX1)
    prim = PRIM_BUF + i * PRIM_SIZE
    for _ in range(7):  # the HUD's 8th sprite (mar2.c RIC_HUD_ICON)
        prim = e.read(prim)
    front = tuple(e.read_bytes(prim + 0x0C, 2))
    j = struct.unpack("<h", e.read_bytes(ult_symbol("g_Mar2BackPrim"), 2))[0]
    if j < 0:
        return front, None
    back = PRIM_BUF + j * PRIM_SIZE
    shown = (e.read_bytes(back + 7, 1)[0] == PRIM_GT4 and  # an allocated sprite, drawn
             struct.unpack("<H", e.read_bytes(back + 0x32, 2))[0] != DRAW_HIDE)
    return front, tuple(e.read_bytes(back + 0x0C, 2)) + (shown,)


@scenario(start="entrance", disc=COOP_DISC)
def ultimate_maria_subweapons(run):
    """Her two slots, as on the PSP (mar2.c): a pickup fills the other slot (a dagger is her Cat,
    a Bible her Doll), Circle swaps them, and the HUD shows both, hers in front."""
    e, mb = run.emu, mailbox(run)
    reload_as(run, mb, CHAR_ULT_MARIA)
    e.write(FRONT, DAGGER)  # she throws the Cat
    e.write(SUBWEAPON, AXE)  # a stage pickup: the Cardinal, in the other slot
    run.step(30)
    run.expect((e.read(FRONT), e.read(SUBWEAPON)) == (DAGGER, AXE), "Cat in front, Cardinal behind",
               front=e.read(FRONT), other=e.read(SUBWEAPON))
    front, back = hud_icons(e)
    run.expect(front == ICON_UV[DAGGER] and back is not None and back[:2] == ICON_UV[AXE] and back[2],
               "the HUD shows the Cat in front and the Cardinal behind", front=front, back=back)
    e.write(SUBWEAPON, BIBLE)  # a Bible picked up: the Doll replaces the Cardinal
    run.step(30)
    run.expect((e.read(FRONT), e.read(SUBWEAPON)) == (DAGGER, BIBLE), "a Bible gives her the Doll, behind",
               front=e.read(FRONT), other=e.read(SUBWEAPON))
    run.step(2, "circle")
    run.step(30)
    run.expect((e.read(FRONT), e.read(SUBWEAPON)) == (BIBLE, DAGGER), "Circle swaps them",
               front=e.read(FRONT), other=e.read(SUBWEAPON))
    front, back = hud_icons(e)
    run.expect(front == ICON_UV[BIBLE] and back is not None and back[:2] == ICON_UV[DAGGER] and back[2],
               "the HUD turns with them: the Doll in front", front=front, back=back)
    from coop_env import TOOLS
    e.screenshot().save(TOOLS["out"] / "ultimate_maria_subweapons" / "hud.png")  # the evidence


# Her as the partner (M13 step 3): her partner build, from the blob's second part.
@session_scenario(starts=("entrance", "entrance"), characters=(CHAR_ALUCARD, CHAR_ULT_MARIA))
def partner_body_alucard_and_ultimate_maria(run):
    """Alucard's game, an Ultimate Maria partner: her own partner build, not Co-op Maria's."""
    from scenarios_m13 import _partner_pair
    _partner_pair(run, CHAR_ALUCARD, CHAR_ULT_MARIA)


@session_scenario(starts=("entrance", "entrance"), characters=(CHAR_MARIA, CHAR_ULT_MARIA))
def partner_body_maria_and_ultimate_maria(run):
    """Co-op Maria's game, an Ultimate Maria partner: the two Marias' blobs side by side."""
    from scenarios_m13 import _partner_pair
    _partner_pair(run, CHAR_MARIA, CHAR_ULT_MARIA)


@session_scenario(starts=("entrance", "entrance"), characters=(CHAR_ULT_MARIA, CHAR_ALUCARD))
def partner_body_ultimate_maria_and_alucard(run):
    """Ultimate Maria's game, an Alucard partner."""
    from scenarios_m13 import _partner_pair
    _partner_pair(run, CHAR_ULT_MARIA, CHAR_ALUCARD)


@session_scenario(starts=("no1", "entrance"), characters=(CHAR_ALUCARD, CHAR_ULT_MARIA))
def boss_doppleganger_alucard_and_ultimate_maria(run):
    """Alucard walks into the Doppleganger's room, Ultimate Maria is pulled in, both hurt it, it
    dies once and both worlds record the kill (session_m8.party_boss)."""
    from session_m8 import party_boss
    party_boss(run, CHAR_ALUCARD, CHAR_ULT_MARIA)


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


@session_scenario(starts=("entrance", "entrance"), characters=(4, CHAR_ALUCARD))
def partner_body_saturn_maria_and_alucard(run):
    """Saturn Maria's game, an Alucard partner."""
    from scenarios_m13 import _partner_pair
    _partner_pair(run, 4, CHAR_ALUCARD)


@session_scenario(starts=("entrance", "entrance"), characters=(CHAR_MARIA, 4), full=True)
def partner_body_maria_and_saturn_maria(run):
    """Co-op Maria's game, a Saturn Maria partner: three blobs, two partner areas."""
    from scenarios_m13 import _partner_pair
    _partner_pair(run, CHAR_MARIA, 4)


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
