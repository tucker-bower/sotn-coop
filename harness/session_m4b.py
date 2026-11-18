"""M4b: fixes from playtest 1 (design/M4b-playtest-fixes.md)."""


from session import Session, SessionRun, session_scenario  # first: puts `link` on the path

from link.mailbox import ROLE_AUTHORITY, ROLE_GUEST


def roles(s):
    return s.a.mailbox("self_presence").role, s.b.mailbox("self_presence").role


LCK_TOTAL = 0x80097BE4   # g_Status.statsTotal[STAT_LCK]
LCK_BASE = 0x80097BC4    # g_Status.statsBase[STAT_LCK]: the game recomputes the total from it


def lucky(g):
    g.write(LCK_BASE, 4000, "<i")
    g.write(LCK_TOTAL, 4000, "<i")
E_PRIZE_DROP_NO3 = 0x03  # NO3's entity id for money/heart drops


def drops(g):
    import struct
    raw = g.read_bytes("g_Entities", 0xBC * 256)
    return {s for s in range(160, 192) if struct.unpack_from("<H", raw, s * 0xBC + 0x26)[0] == E_PRIZE_DROP_NO3}


def brightness(img):
    return sum(img.convert("L").get_flattened_data()) / (img.width * img.height)


CANDLE_SLOT, CANDLE_X = 71, 1248  # a wall candle in the entrance hall (layout entry)


PRIM_ENV, POOL, POOL_N, DR_ENV_SIZE = 7, 0x800974AC, 16, 0x40  # DRA's DR_ENV pool (D_800974AC)


@session_scenario()
def guest_takes_heart(run):
    """D66 (was the known gap D51): a heart the guest picks up is the guest's. A large heart is
    dropped in the hall (harness: a prize drop entity made in A's world, as a kill makes one);
    B, the guest, walks over it: B's hearts go up, A's don't, and it's gone from both worlds."""
    from module import stage_symbol
    from session_shared import into_hall
    a, b = run.s.a, run.s.b
    into_hall(run)
    run.expect(roles(run.s) == (ROLE_AUTHORITY, ROLE_GUEST), "A is the authority, B the guest", roles=roles(run.s))
    slot = next(k for k in range(160, 192) if not a.read(a.entity(k) + 0x26, "<H"))
    e = a.entity(slot)
    a.write_bytes(e, bytes(0xBC))
    a.write(e, E_PRIZE_DROP_NO3, "<H", 0x26)
    a.write(e, stage_symbol("stno3", "EntityPrizeDrop"), "<I", 0x28)
    a.write(e, 1, "<H", 0x30)  # params: ITEMDROP_LARGE_HEART
    drop_x = b.snapshot()["world_x"] + 40
    a.write(e, drop_x - a.read("g_Tilemap", "<h", 0xA), "<h", 2)
    a.write(e, b.snapshot()["world_y"] - 40 - a.read("g_Tilemap", "<h", 0xE), "<h", 6)
    hearts = lambda g: g.read("g_Status", "<i", 0x244)
    for g in (a, b):
        g.write("g_Status", 10, "<i", 0x244)
    run.step(60)  # it falls to the floor
    run.expect(slot in drops(a) and slot in drops(b), "the heart is there in both worlds")
    ha, hb = hearts(a), hearts(b)
    for i in range(300):
        run.step(1, p1=("", "right"))
        if hearts(b) != hb:
            break
    run.step(20)
    run.expect(hearts(b) > hb, "B's hearts went up", was=hb, now=hearts(b))
    run.expect(hearts(a) == ha, "A's didn't", was=ha, now=hearts(a))
    run.expect(slot not in drops(a) and slot not in drops(b), "the drop is gone from both worlds")


ITEM_LIFE_APPLE = 0x92


ELEVATOR_ROOM, ELEVATOR_SLOT, ELEVATOR_X, ELEVATOR_Y = 176, 96, 144, 96  # NZ0: a tall shaft


