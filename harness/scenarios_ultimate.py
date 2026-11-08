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


def saturn_maria_blob():
    """Saturn Maria's CharBlob from the dev build (characters/maria-saturn: Ultimate's converters
    run on the dev machine), Richter's sounds; None if she isn't built. Phase 1 of her design."""
    from coop_env import REPO
    ovl = REPO / "build/coop/maria-saturn/SATMAR.BIN"
    if not ovl.exists():
        return None
    o = ovl.read_bytes()
    from link.mailbox import CHAR_SAT_MARIA
    return struct.pack("<8I", 0x52414843, CHAR_SAT_MARIA, len(o), 0, 0, 0, 0, 0) + o + bytes(-len(o) % 4) + bytes(4)


@scenario(start="entrance", disc=COOP_DISC)
def saturn_maria_in_the_castle(run):
    """Saturn Maria (SOTN Ultimate's, phase 1): an Alucard save loads as her, her overlay in
    Richter's slot and her code in the 8MB, she walks and attacks, and loads back as Alucard."""
    from link.mailbox import CHAR_BLOB_ADDR, CHAR_SAT_MARIA
    from coop_env import TOOLS
    e, mb = run.emu, mailbox(run)
    blob = saturn_maria_blob()
    run.expect(blob is not None, "her dev build is there (make -C characters/maria-saturn)")
    e.write_bytes(CHAR_BLOB_ADDR, blob)
    reload_as(run, mb, CHAR_SAT_MARIA)
    run.expect(mb.self_presence().character == CHAR_SAT_MARIA, "the game reports Saturn Maria",
               character=mb.self_presence().character)
    # her player table (g_PlOvl); the frame table after it is hers to rewrite: she unpacks her
    # LZSS images into buffers every frame and points it at them
    run.expect(e.read_bytes(RICHTER_OVERLAY, 32) == blob[BLOB_HEAD:BLOB_HEAD + 32], "Richter's slot holds her overlay")
    s0 = e.snapshot()
    s = run.play(walker("left", attack_every=12), 300)
    e.screenshot().save(TOOLS["out"] / "saturn_maria_in_the_castle" / "walk.png")
    run.expect((s["world_x"] < s0["world_x"] - 50 or s["room"] != s0["room"]) and s["hp"] > 0,
               "she walks and attacks in the castle", moved=s0["world_x"] - s["world_x"], room=s["room"])
    reload_as(run, mb, CHAR_ALUCARD)
    run.expect(mb.self_presence().character == CHAR_ALUCARD, "and loads back as Alucard")
