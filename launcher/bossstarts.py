"""Boss starts: one debug start outside each boss of the first castle, with the progress a player
would usually have by then (level, gold, gear, relics, vessels, story flags, earlier bosses beaten,
the map of the areas visited so far). Made on the player's PC from their own disc, like the other
debug starts (debugstarts.py); savestates hold game RAM, so they're never shipped (D9, D69).

How one is made, from the castle entrance:
1. Progress is written into RAM (g_Status, castle flags, time attack records, the map).
2. The co-op module saves it as a joint save and loads it again (CMD_SAVE_NOW, CMD_LOAD_SAVE),
   as after loading a memory card: the game recomputes attack, defense and stats from the gear.
3. The player arrives outside the boss's door (CMD_ARRIVE).
4. Check: from a copy, a bot walks in until the boss is there (presence BOSS flag) or its arena
   loads. A start that fails the check is still made, and says so in its description.

The route and the loadouts follow a typical first playthrough (the critical path in
docs/research.md); they're judgment calls, and each is one table row below."""

import struct

# Ids from the decomp's include/items.h (hand items and body items are separate lists).
HAND = {"empty": 0, "leather shield": 5, "knight shield": 6, "herald shield": 9, "shaman shield": 12,
        "basilard": 18, "short sword": 19, "gladius": 86, "cutlass": 88, "bekatowa": 92,
        "holy sword": 115, "morningstar": 129, "potion": 159, "high potion": 160,
        "alucard shield": 16, "alucard sword": 123, "elixir": 161}
BODY = {"no armor": 0, "hide cuirass": 2, "bronze cuirass": 3, "silver plate": 6, "gold plate": 7,
        "platinum mail": 8, "ice mail": 12, "mirror cuirass": 13, "no head": 26, "sunglasses": 27,
        "goggles": 32, "holy glasses": 34, "steel helm": 35, "stone mask": 36, "no cape": 48,
        "cloth cape": 49, "crystal cloak": 52, "blood cloak": 54, "no accessory": 57, "moonstone": 58,
        "gold ring": 72, "silver ring": 73, "alucard mail": 15, "dragon helm": 45, "twilight cloak": 56,
        "ring of arcana": 75, "talisman": 83}
RELICS = ["soul of bat", "fire of bat", "echo of bat", "force of echo", "soul of wolf", "power of wolf",
          "skill of wolf", "form of mist", "power of mist", "gas cloud", "cube of zoe", "spirit orb",
          "gravity boots", "leap stone", "holy symbol", "faerie scroll", "jewel of open", "merman statue",
          "bat card", "ghost card", "faerie card", "demon card", "sword card", "jp 0", "jp 1",
          "heart of vlad", "tooth of vlad", "rib of vlad", "ring of vlad", "eye of vlad"]
CARDS = {"bat card", "ghost card", "faerie card", "demon card", "sword card"}  # familiars: found, not summoned
SUBWEAPONS = {"dagger": 1, "axe": 2, "holy water": 3, "cross": 4}
EVENTS = {  # time attack events (include/game.h): a nonzero record = done
    "olrox": 1, "doppleganger10": 2, "granfaloon": 3, "minotaur & werewolf": 4, "scylla": 5,
    "slogra & gaibon": 6, "hippogryph": 7, "succubus": 9, "karasuman": 10, "cerberus": 13,
    "richter": 14, "lesser demon": 17, "meet death": 23, "holy glasses": 24, "librarian": 25,
    "maria": 26,
    # the inverted castle's
    "dracula": 0, "beelzebub": 8, "fake trevor, grant & sypha": 11, "death": 12, "medusa": 15,
    "the creature": 16, "doppleganger40": 18, "akmodan ii": 19, "darkwing bat": 20, "galamoth": 21}
FLAGS = {  # include/castle_flags.h: story flags set by the time each boss is reached
    "slogra & gaibon": [0x84], "maria in nz0": [0x85], "librarian": [0x72], "maria after hippogryph": [0x62],
    "maria in dai": [0x63], "richter after m&w": [0xB4], "scylla wyrm": [0xC5], "scylla": [0xC3],
    "ferryman": [0xC2, 0xC8, 0xC9], "succubus": [0xD4], "demon switch": [0x50], "cen open": [0x00],
    "maria in cen": [0xD8], "no4 open": [0x01], "outer wall elevator": [0x10],
    "inverted castle": [0x96]}  # INVERTED_CASTLE_UNLOCKED
WARPS = {"NP3": 0x80, "CHI": 0x40, "NO1": 0x20, "TOP": 0x10, "NO2": 0x08}  # WRP_UNLOCKS bits

# Stage ids (include/game.h) and the areas a player has usually explored by each boss.
STAGES = {"NO0": 0x00, "NO1": 0x01, "LIB": 0x02, "CAT": 0x03, "NO2": 0x04, "CHI": 0x05, "DAI": 0x06,
          "CEN": 0x08, "BO3": 0x1B, "BO6": 0x18, "NO4": 0x09, "ARE": 0x0A, "TOP": 0x0B, "NZ0": 0x0C, "NZ1": 0x0D, "DRE": 0x12,
          "NO3": 0x41,
          # the inverted castle (STAGE_INVERTEDCASTLE_FLAG) and its boss stages
          "RNO1": 0x21, "RNO2": 0x24, "RCHI": 0x25, "RDAI": 0x26, "RNO4": 0x29, "RARE": 0x2A, "RNZ0": 0x2C,
          "RCAT": 0x23, "RNZ1": 0x2D, "RBO0": 0x3E, "RBO1": 0x3D, "RBO2": 0x3C, "RBO3": 0x3B, "RBO4": 0x3A, "RBO5": 0x39,
          "RBO6": 0x38, "RBO7": 0x37, "RBO8": 0x36}

# name: area, stage, arrive (room id, x, y), walk, level, gold, life ups, heart ups,
#       gear (right hand, left hand, head, body, cape, accessory 1, accessory 2), subweapon,
#       relics, areas explored, story flags, events done (bosses beaten...), extra inventory
B = []


def boss(name, area, stage, arrive, walk, level, gold, vessels, gear, sub, relics, areas, flags, done, keep=(),
         check=None, note=""):
    """check: where the bot starts its walk instead, when the way in needs something it can't do
    (mist through bars); note: told to the player."""
    B.append(dict(name=name, area=area, stage=stage, arrive=arrive, walk=walk, level=level, gold=gold,
                  vessels=vessels, gear=gear, sub=sub, relics=relics, areas=areas, flags=flags, done=done,
                  keep=keep, check=check, note=note))


R1 = ["cube of zoe"]
R2 = R1 + ["spirit orb"]
R3 = R2 + ["faerie scroll", "jewel of open", "soul of wolf", "faerie card"]
R4 = R3 + ["leap stone"]
R5 = R4 + ["form of mist"]
R6 = R5 + ["soul of bat"]
R7 = R6 + ["fire of bat", "ghost card", "power of mist"]
R8 = R7 + ["echo of bat", "sword card", "gravity boots"]
R9 = R8 + ["merman statue"]
R10 = R9 + ["holy symbol"]
R11 = R10 + ["demon card"]
A1 = ["NO3", "NZ0"]
A2 = A1 + ["NO0", "NO1"]
A3 = A2 + ["LIB", "DAI"]
A4 = A3 + ["TOP", "ARE"]
A5 = A4 + ["NZ1"]
A6 = A5 + ["NO2"]
A7 = A6 + ["NO4"]
A8 = A7 + ["CHI"]
A9 = A8 + ["CAT"]
F1 = ["slogra & gaibon", "maria in nz0"]
F2 = F1 + ["librarian", "outer wall elevator"]
F3 = F2 + ["maria after hippogryph", "maria in dai"]
F4 = F3 + ["richter after m&w", "no4 open"]
F5 = F4 + ["succubus", "ferryman"]
F6 = F5 + ["scylla wyrm", "scylla"]
F7 = F6 + ["demon switch"]
D1 = ["meet death"]
D2 = D1 + ["slogra & gaibon", "maria"]
D3 = D2 + ["doppleganger10", "librarian"]
D4 = D3 + ["hippogryph"]
D5 = D4 + ["minotaur & werewolf"]
D6 = D5 + ["lesser demon"]
D7 = D6 + ["karasuman"]
D8 = D7 + ["olrox"]
D9 = D8 + ["succubus"]
D10 = D9 + ["scylla"]
D11 = D10 + ["cerberus"]
D12 = D11 + ["granfaloon"]

boss("Slogra & Gaibon", "Alchemy Laboratory", "NZ0", (152, 200, 400), "left", 8, 600, (1, 1),
     ("short sword", "leather shield", "no head", "hide cuirass", "cloth cape", "no accessory", "no accessory"),
     "dagger", R1, A1, [], D1)
boss("Doppleganger10", "Outer Wall", "NO1", (0x60, 40, 135), "left", 12, 2000, (2, 2),
     ("gladius", "leather shield", "sunglasses", "hide cuirass", "cloth cape", "no accessory", "no accessory"),
     "dagger", R2, A2, F1, D2, keep=("short sword", "basilard"))
boss("Hippogryph", "Royal Chapel", "DAI", (0x18, 640, 132), "right", 16, 5000, (3, 3),
     ("gladius", "leather shield", "stone mask", "bronze cuirass", "cloth cape", "no accessory", "no accessory"),
     "axe", R3, A3, F2, D3, keep=("short sword", "basilard", "sunglasses", "hide cuirass"))
boss("Minotaur & Werewolf", "Colosseum", "ARE", (0x20, 1150, 132), "right", 19, 8000, (4, 4),
     ("cutlass", "leather shield", "goggles", "silver plate", "cloth cape", "no accessory", "no accessory"),
     "axe", R4, A4, F3, D4, keep=("gladius", "morningstar", "stone mask", "bronze cuirass"))
boss("Lesser Demon", "Long Library", "LIB", (0, 1100, 700), "left", 21, 10000, (5, 4),
     ("cutlass", "knight shield", "goggles", "silver plate", "blood cloak", "no accessory", "no accessory"),
     "axe", R5, A4, F4, D5, keep=("gladius", "leather shield", "cloth cape"), check=(0, 800, 700),
     note="mist through the bars")
boss("Karasuman", "Clock Tower", "NZ1", (8, 60, 132), "left", 23, 13000, (6, 5),
     ("cutlass", "knight shield", "goggles", "mirror cuirass", "blood cloak", "no accessory", "no accessory"),
     "axe", R6, A5, F4, D6, keep=("gladius", "silver plate"))
boss("Olrox", "Olrox's Quarters", "NO2", (0x58, 56, 132), "left", 26, 17000, (8, 6),
     ("bekatowa", "shaman shield", "steel helm", "gold plate", "blood cloak", "no accessory", "no accessory"),
     "holy water", R7, A6, F4, D7, keep=("cutlass", "knight shield", "goggles", "mirror cuirass"))
boss("Succubus", "Underground Caverns (Nightmare)", "DRE", (0, 16, 180), "right", 28, 21000, (9, 7),
     ("holy sword", "shaman shield", "steel helm", "gold plate", "blood cloak", "no accessory", "no accessory"),
     "holy water", R8, A7, F4, D8, keep=("bekatowa", "cutlass", "knight shield"))
# In her arena (room 0), right of her: the Crystal Cloak room (24) is behind her, and walking in
# from there, a barrier (E_UNK_3E) pushes the player back out until she's beaten.
boss("Scylla", "Underground Caverns", "BO3", (0, 650, 150), "left", 30, 24000, (10, 8),
     ("holy sword", "herald shield", "steel helm", "gold plate", "blood cloak", "gold ring", "no accessory"),
     "holy water", R9, A7, F5 + ["scylla wyrm"], D9, keep=("bekatowa", "shaman shield"))
boss("Cerberus", "Abandoned Mine", "CHI", (8, 390, 132), "right", 32, 28000, (11, 9),
     ("holy sword", "herald shield", "steel helm", "ice mail", "crystal cloak", "gold ring", "moonstone"),
     "holy water", R10, A8, F6, D10, keep=("bekatowa", "gold plate", "blood cloak"))
boss("Granfaloon", "Catacombs", "CAT", (0x20, 56, 132), "left", 34, 32000, (12, 10),
     ("holy sword", "herald shield", "steel helm", "ice mail", "crystal cloak", "gold ring", "moonstone"),
     "holy water", R11, A9, F7, D11, keep=("bekatowa", "gold plate"))
boss("Richter", "Castle Keep", "BO6", (0, 240, 179), "left", 38, 40000, (14, 12),
     ("holy sword", "herald shield", "steel helm", "platinum mail", "crystal cloak", "gold ring", "silver ring"),
     "holy water", R11, A9 + ["CEN"], F7 + ["cen open", "maria in cen"], D12 + ["holy glasses"],
     keep=("holy glasses", "ice mail", "moonstone"),
     note="at his door; Holy Glasses in the bag")

# The inverted castle (v1.1, D114): after freeing Richter (the Holy Glasses on, Shaft's orb).
# Each start is in the room next to its boss's door (the door is a map cell of the stage whose
# room loads the boss's stage: g_RoomBossTeleports), so the boss spawns once the partner is
# linked, with co-op's 2x HP. Positions as the player sees them (Arrive pre-mirrors), each tried
# with a bot walking in. Dracula's is in his own stage: the way there is Shaft's room, whose
# scene and elevator a bot doesn't get through yet. The route (relic order) is a typical one;
# each beaten boss adds its Vlad relic and a level.
INV_GEAR = ("alucard sword", "alucard shield", "dragon helm", "alucard mail", "twilight cloak",
            "ring of arcana", "talisman")
INV_KEEP = ("holy sword", "herald shield", "steel helm", "platinum mail", "crystal cloak", "gold ring",
            "silver ring", "holy glasses")
R12 = R11 + ["power of wolf", "skill of wolf", "gas cloud", "force of echo", "bat card"]
F8 = F7 + ["cen open", "maria in cen", "inverted castle"]
D13 = D12 + ["holy glasses", "richter"]
INVERTED = []


def inverted(name, area, stage, arrive, walk, relic=None, event=None):
    k = len(INVERTED)
    done = D13 + [r["event"] for r in INVERTED if r["event"]]
    relics = R12 + [r["relic"] for r in INVERTED if r["relic"]]
    row = dict(name=name, area=area, stage=stage, arrive=arrive, walk=walk, level=40 + k, gold=50000 + 6000 * k,
               vessels=(16 + k, 14 + k), gear=INV_GEAR, sub="holy water", relics=relics, areas=A9 + ["CEN"],
               flags=F8, done=done, keep=INV_KEEP, check=None, note="", inverted=True, relic=relic, event=event)
    INVERTED.append(row)
    B.append(row)


inverted("The Creature", "Reverse Outer Wall", "RNO1", (96, 232, 132), "right", "tooth of vlad", "the creature")
inverted("Darkwing Bat", "Reverse Clock Tower", "RNZ1", (112, 24, 132), "left", "ring of vlad", "darkwing bat")
inverted("Akmodan II", "Death Wing's Lair", "RNO2", (88, 1000, 132), "right", "rib of vlad", "akmodan ii")
inverted("Medusa", "Anti-Chapel", "RDAI", (40, 744, 132), "right", "heart of vlad", "medusa")
inverted("Death", "Cave", "RCHI", (8, 24, 132), "left", "eye of vlad", "death")
inverted("Doppleganger40", "Reverse Caverns", "RNO4", (232, 1256, 132), "right", None, "doppleganger40")
inverted("Fake Trevor, Grant & Sypha", "Reverse Colosseum", "RARE", (48, 1256, 132), "right", None,
         "fake trevor, grant & sypha")
inverted("Beelzebub", "Necromancy Laboratory", "RNZ0", (152, 488, 132), "right", None, "beelzebub")
inverted("Galamoth", "Floating Catacombs", "RCAT", (32, 232, 132), "right", None, "galamoth")
# Dracula talks first (about 2,900 frames). Started in his stage, he spawns before the partner is
# linked, at 1x HP: the tests step out (`out`) and back in first.
inverted("Dracula", "Reverse Center", "RBO6", (16, 112, 180), "right", None, "dracula")
INVERTED[-1]["out"] = ("NO0", 80, 728, 135)

STATUS_LEVEL, STATUS_EXP, STATUS_GOLD = 0x284, 0x288, 0x28C
STATUS_HP, STATUS_HEARTS, STATUS_MP, STATUS_STATS = 0x23C, 0x244, 0x24C, 0x254
STATUS_SUB, STATUS_EQUIP, STATUS_TIMER = 0x298, 0x29C, 0x2CC
HAND_COUNT, BODY_COUNT = 0x26, 0xCF  # equipHandCount[169], equipBodyCount[90]
RECORDS = 0x30                        # g_Settings.timeAttackRecords
WRP_UNLOCKS = 0xD0
LEVEL_HP = [1, 3, 6, 10, 20, 30, 40, 50, 100, 200]  # g_LevelHPIncrease (src/dra/5D5BC.c)
EXP_NEXT = [0, 0, 100, 250, 450, 700, 1000, 1350, 1750, 2200, 2700, 3250, 3850, 4500, 5200, 5950, 6750,
            7600, 8500, 9450, 10450, 11700, 13200, 15100, 17500, 20400, 23700, 27200, 30900, 35000, 39500,
            44500, 50000, 56000, 61500, 68500, 76000, 84000, 92500, 101500, 110000, 120000, 130000,
            140000, 150000, 160000, 170000, 180000, 190000, 200000]  # g_ExpNext, levels 0-49


# Scene starts (Tucker, 2026-10-26): one before each story scene of the first castle, with the
# progress of the boss nearest before it in the story (its row: `like`), and the scene's own
# "seen" castle flag cleared (include/castle_flags.h). Each starts in the room before the scene's,
# found from the decomp's room tables (assets/st/<stage>/rooms.json, entity_layouts.json): walking
# on starts the scene. Bosses whose arena opens with a scene (Succubus, Richter, Minotaur &
# Werewolf) have it in their boss start.
S = []


def scene(name, area, stage, arrive, walk, like, unset=(), check=None, note="", undone=()):
    """undone: events of `like`'s row not done yet (the scene comes before that boss)."""
    row = dict(next(b for b in B if b["name"] == like))
    row.update(name=name, area=area, stage=stage, arrive=arrive, walk=walk, check=check, note=note,
               unset=tuple(unset), scene=True, done=[d for d in row["done"] if d not in undone],
               like=like, before=bool(undone))
    S.append(row)


def story_order(b):
    """Where a boss or scene start comes in a playthrough: by its boss; a scene after its boss's
    fight, or before it if the scene comes first."""
    k = next(i for i, x in enumerate(B) if x["name"] == b.get("like", b["name"]))
    return (k, (-1 if b.get("before") else 1) if b.get("scene") else 0)


# Walking right meets Maria (the time attack event "maria" is her first meeting).
scene("Maria in the Marble Gallery", "Marble Gallery", "NO0", (80, 728, 135), "right", "Doppleganger10",
      undone=["maria"])


# From the right: her scene steers Alucard left (from the left he walks straight back out, and
# walking in again replays it).
scene("Maria in the Alchemy Lab", "Alchemy Laboratory", "NZ0", (16, 40, 128), "left", "Slogra & Gaibon",
      unset=[0x85])  # MET_MARIA_IN_NZ0
# In his room, at its right edge: walking left from there starts his scene, which steers the
# player in (to x 0x74). At x 120 the player was already past where it starts (M12 v1.0).
scene("The Librarian", "Long Library", "LIB", (32, 236, 120), "left", "Lesser Demon", unset=[0x72])  # MET_LIBRARIAN
scene("Maria in the Royal Chapel", "Royal Chapel", "DAI", (8, 40, 128), "left", "Minotaur & Werewolf",
      unset=[0x63])  # MET_MARIA_IN_DAI
# In the Center, at its right edge on Maria's floor (the way in is a door there), out of the
# camera's reach of the scene (x 384).
scene("Maria in the Center: the Holy Glasses", "Center", "CEN", (8, 728, 455), "left", "Richter",
      unset=[0xD8])  # MET_MARIA_IN_CEN
scene("The Castle Keep", "Castle Keep", "TOP", (16, 496, 896), "right", "Richter")


def apply(e, b, base, rooms):
    """Writes boss start b's progress over the entrance status `base` (bytes of g_Status)."""
    st = bytearray(base)
    put = lambda off, v: struct.pack_into("<i", st, off, v)
    get = lambda off: struct.unpack_from("<i", st, off)[0]
    lvl = b["level"]
    # Level ups as the game gives them (CheckAndDoLevelUp), at their average: MP +4.5, hearts +2,
    # HP by the level's band, each stat +1 half the time (plus the mercy point).
    hp = get(STATUS_HP + 4) + sum(LEVEL_HP[k // 10] for k in range(2, lvl + 1)) + 5 * b["vessels"][0]
    hearts = get(STATUS_HEARTS + 4) + 2 * (lvl - 1) + 5 * b["vessels"][1]
    mp = get(STATUS_MP + 4) + (9 * (lvl - 1)) // 2
    for off, v in ((STATUS_HP, hp), (STATUS_HEARTS, hearts), (STATUS_MP, mp)):
        put(off, v)
        put(off + 4, v)
    for i in range(4):
        put(STATUS_STATS + 4 * i, get(STATUS_STATS + 4 * i) + round(0.58 * (lvl - 1)))
    put(STATUS_LEVEL, lvl)
    put(STATUS_EXP, EXP_NEXT[lvl] + 40)
    put(STATUS_GOLD, b["gold"])
    put(STATUS_SUB, SUBWEAPONS[b["sub"]])
    for i, name in enumerate(b["gear"]):
        put(STATUS_EQUIP + 4 * i, (HAND if i < 2 else BODY)[name])
    for name in b["keep"]:
        if name in HAND:
            st[HAND_COUNT + HAND[name]] = 1
        else:
            st[BODY_COUNT + BODY[name]] = 1
    st[HAND_COUNT + HAND["potion"]] = 3
    st[HAND_COUNT + HAND["high potion"]] = 1 if lvl > 20 else 0
    for name in b["relics"]:
        st[RELICS.index(name)] = 1 if name in CARDS else 3  # found (+ on, for abilities)
    play_minutes = lvl * 9
    put(STATUS_TIMER, play_minutes // 60)
    put(STATUS_TIMER + 4, play_minutes % 60)
    e.write_bytes("g_Status", bytes(st))

    for name in b["flags"]:
        for f in FLAGS[name]:
            e.write("g_CastleFlags", 1, "<B", f)
    for f in b.get("unset", ()):  # a scene start: its scene not seen yet
        e.write("g_CastleFlags", 0, "<B", f)
    e.write("g_CastleFlags", sum(bit for a, bit in WARPS.items() if a in b["areas"]), "<B", WRP_UNLOCKS)
    for k, name in enumerate(b["done"]):
        e.write("g_Settings", 1000 + 100 * k, "<i", RECORDS + 4 * EVENTS[name])

    cells = 0
    for area in b["areas"]:
        for x, y in rooms.get(area, ()):
            idx, bit = (x >> 2) + y * 16, 1 << ((3 - (x & 3)) * 2)
            if not e.read("g_CastleMap", "<B", idx) & bit:
                e.write("g_CastleMap", e.read("g_CastleMap", "<B", idx) | bit, "<B", idx)
                cells += 1
    e.write("g_RoomCount", e.read("g_RoomCount") + cells)


def survey(e):
    """The map cells of the stage that's loaded (its room table, g_api.o.rooms; loading rooms left out)."""
    rooms = e.read("g_api", "<I", 0x10)
    cells = []
    for k in range(256):
        left, top, right, bottom, _, tileset = e.read_bytes(rooms, 6, 8 * k)
        if left == 0x40:
            break
        if tileset != 0xFF:
            cells += [(x, y) for x in range(left, right + 1) for y in range(top, bottom + 1)]
    return cells


def about(b):
    return (f"{b['area']}. Level {b['level']}, {b['gold']} gold, {b['gear'][0]}, {len(b['relics'])} relic"
            f"{'s' * (len(b['relics']) > 1)}"
            f" — {b['note'] or 'walk ' + b['walk']}")
