"""The game <-> host mailbox in RAM. Mirrors module/link.h: keep the two in sync."""

import struct
from dataclasses import astuple, dataclass

COOP_MAGIC = 0x504F4F43  # 'COOP'
LINK_VERSION = 11
# Hand weapons (link.h's CoopWeapon, module/weapons.c), in the 8MB, outside g_CoopLink
WEAPON_SELF, WEAPON_PARTNER, WEAPON_HAND_SIZE = 0x80710000, 0x80720000, 0x8000
WEAPON_MAGIC, WEAPON_SIZE = 0x534E5057, 0x7320
# M13: the partner's status for its body (link.h's CoopStatus): g_Status's two ranges
STATUS_PARTNER, STATUS_MAGIC = 0x80730000, 0x53544154
STATUS_RANGES = ((0x80097BA0, 0x48), (0x80097BFC, 0x34))

IN_PLAY, SPRITE, PAUSED, BUSY, DEAD, BOSS, CUTSCENE, CS_FOLLOWER = 1, 2, 4, 8, 16, 32, 64, 128  # CoopPresence.flags

_PRESENCE = struct.Struct("<BBBBHHhhhhhHHHIHhhHhhHH")  # CoopPresence, 0x2C bytes
ROLE_NONE, ROLE_AUTHORITY, ROLE_GUEST = 0, 1, 2
_HEADER = struct.Struct("<III")                # magic, version, heartbeat
SELF, PARTNER = 0x0C, 0x38                     # offsets in CoopLink
PARTNER_AGE = 0x64
OUT_RING, IN_RING, DROPPED = 0x68, 0x870, 0x1078
RING_SIZE, EVENT_SIZE = 256, 8                 # CoopRing: u32 head, u32 tail, CoopEvent[256]
EV_FLAG, EV_MAP, EV_ITEM, EV_GRANT, EV_GOLD = 1, 2, 3, 4, 5
EV_HIT, EV_HIT2, EV_SPAWN, EV_SPAWN2, EV_SPAWN3, EV_RECORD, EV_TAKEN, EV_EXP = 6, 7, 8, 9, 10, 11, 12, 13
CMD, CMD_DONE, SAVE_SEQ, SAVE_OUT, SAVE_IN = 0x107C, 0x108C, 0x1090, 0x1094, 0x2260
SAVE_DATA_SIZE = 0x11CC
CMD_ARRIVE, CMD_LOAD_SAVE, CMD_SAVE_NOW, CMD_GAME_OVER = 1, 2, 3, 4
_COMMAND = struct.Struct("<IHHHhhH")
SAVE_BLOCK, CARD_RESULT, RANK = 0x342C, 0x3430, 0x3434
SNAP_OUT_SEQ, SNAP_OUT, SNAP_IN_SEQ, SNAP_IN = 0x3438, 0x3440, 0x12440, 0x12448  # size word follows each seq
CONTROL = 0x21448
CHARACTER, OPTIONS, PAD_EXTRA = 0x2144C, 0x21450, 0x21454  # host writes (M8)
SELF_SPRITES, PARTNER_SPRITES = 0x21458, 0x2163C  # u32 count, then CoopSprite[24] (0x14 each): sprites.c (M12)
SPRITE_SIZE, N_SPRITES = 0x14, 24
SELF_PRIMS, PARTNER_PRIMS = 0x21820, 0x21E24  # u32 count, then Primitive[32] less next (0x30 each)
SELF_PAD, PARTNER_PAD = 0x22428, 0x2242C  # M13: each player's buttons, with the presence
PRIM_SIZE, N_PRIMS = 0x30, 32
CHAR_ALUCARD, CHAR_RICHTER, CHAR_MARIA = 0, 1, 2
OPT_SHORTCUTS = 1  # options: one-button moves (design/M8b §3.2)
OPT_PARTNER_SIM = 2  # options: M13 spike, the partner simulated by the game's player code (module/partner.c)
OPT_SPELL_SHIFT = 8  # options: Alucard's spell per right-stick direction (up, right, down, left), 4 bits each: SpellIds + 1
SPELLS = ("Dark Metamorphosis", "Summon Spirit", "Hellfire", "Tetra Spirit", None, "Soul Steal", None, "Sword Brothers")


def spell_options(spells):
    """OPT_* bits for four spell ids (or None) on the right stick: up, right, down, left."""
    return sum(((s + 1) if s is not None else 0) << (OPT_SPELL_SHIFT + 4 * k) for k, s in enumerate(spells))
CHAR_BLOB_ADDR, CHAR_BLOB_MAGIC = 0x80400000, 0x52414843  # CharBlob (module/link.h)
CONTROL_MUTE_MUSIC = 1
CONTROL_NO_AGGRO = 2
CONTROL_AGGRO_SHIFT = 8  # bits 8-15: a boss's chance (of 256) to switch target, 0 = 128
SNAP_MAX = 0xF000
CARD_OK = 6  # the save room's card state machine: 6 = saved, 7-11 = card errors


@dataclass
class Presence:
    flags: int = 0
    character: int = 0
    flip_x: int = 0
    blend_mode: int = 0
    stage: int = 0
    z_priority: int = 0
    room_left: int = 0
    room_top: int = 0
    x: int = 0
    y: int = 0
    anim_set: int = 0
    anim_cur_frame: int = 0
    palette: int = 0
    draw_flags: int = 0
    frame: int = 0
    room_id: int = 0
    ground_x: int = 0
    ground_y: int = 0
    room_frames: int = 0
    scroll_x: int = 0
    scroll_y: int = 0
    role: int = 0
    aggro_switches: int = 0  # bosses switching to/from the partner so far (tests)
    pad: int = 0  # M13: the player's buttons this frame (CoopLink.selfPad), sent beside the struct

    SIZE = _PRESENCE.size

    def pack(self):
        return _PRESENCE.pack(*astuple(self)[:-1])

    @classmethod
    def unpack(cls, data):
        return cls(*_PRESENCE.unpack(data[:cls.SIZE]))

    @property
    def room(self):
        return self.stage, self.room_left, self.room_top


class Mailbox:
    """g_CoopLink in one game's RAM, through an adapter. Only touch it between frames."""

    def __init__(self, adapter, address):
        self.adapter, self.address = adapter, address
        emu = getattr(adapter, "emu", None)
        if emu is not None and hasattr(emu, "pad_extra_addr"):  # the harness: pads carry rs_* too
            emu.pad_extra_addr = address + PAD_EXTRA

    def header(self):
        return _HEADER.unpack(self.adapter.read_bytes(self.address, _HEADER.size))

    def ready(self):
        magic, version, _ = self.header()
        return magic == COOP_MAGIC and version == LINK_VERSION

    def heartbeat(self):
        return self.header()[2]

    def self_presence(self):
        p = Presence.unpack(self.adapter.read_bytes(self.address + SELF, Presence.SIZE))
        p.pad = struct.unpack("<I", self.adapter.read_bytes(self.address + SELF_PAD, 4))[0]
        return p

    def partner_presence(self):
        p = Presence.unpack(self.adapter.read_bytes(self.address + PARTNER, Presence.SIZE))
        p.pad = struct.unpack("<I", self.adapter.read_bytes(self.address + PARTNER_PAD, 4))[0]
        return p

    def partner_age(self):
        return struct.unpack("<I", self.adapter.read_bytes(self.address + PARTNER_AGE, 4))[0]

    def self_sprites(self):
        """This game's sprites for the partner (sprites.c): raw CoopSprite records."""
        n = min(struct.unpack("<I", self.adapter.read_bytes(self.address + SELF_SPRITES, 4))[0], N_SPRITES)
        return self.adapter.read_bytes(self.address + SELF_SPRITES + 4, n * SPRITE_SIZE) if n else b""

    def self_prims(self):
        """This game's attack primitives for the partner (sprites.c)."""
        n = min(struct.unpack("<I", self.adapter.read_bytes(self.address + SELF_PRIMS, 4))[0], N_PRIMS)
        return self.adapter.read_bytes(self.address + SELF_PRIMS + 4, n * PRIM_SIZE) if n else b""

    def write_partner_prims(self, data):
        n = min(len(data) // PRIM_SIZE, N_PRIMS)
        if n:
            self.adapter.write_bytes(self.address + PARTNER_PRIMS + 4, data[:n * PRIM_SIZE])
        self.adapter.write_bytes(self.address + PARTNER_PRIMS, struct.pack("<I", n))

    def partner_sprite_count(self):
        return struct.unpack("<I", self.adapter.read_bytes(self.address + PARTNER_SPRITES, 4))[0]

    def write_partner_sprites(self, data):
        n = min(len(data) // SPRITE_SIZE, N_SPRITES)
        if n:
            self.adapter.write_bytes(self.address + PARTNER_SPRITES + 4, data[:n * SPRITE_SIZE])
        self.adapter.write_bytes(self.address + PARTNER_SPRITES, struct.pack("<I", n))

    # --- hand weapons (module/weapons.c): each game's copy, and the partner's -----------------
    def self_weapon_seq(self, hand):
        """(magic ok, seq) of this game's copy of that hand's weapon."""
        magic, seq = struct.unpack("<II", self.adapter.read_bytes(WEAPON_SELF + hand * WEAPON_HAND_SIZE, 8))
        return magic == WEAPON_MAGIC, seq

    def self_weapon(self, hand):
        return self.adapter.read_bytes(WEAPON_SELF + hand * WEAPON_HAND_SIZE, WEAPON_SIZE)

    def write_partner_weapon(self, hand, blob):
        """The partner's copy (header last: the game checks its magic)."""
        if len(blob) != WEAPON_SIZE:
            return
        base = WEAPON_PARTNER + hand * WEAPON_HAND_SIZE
        self.adapter.write_bytes(base + 0x20, blob[0x20:])
        self.adapter.write_bytes(base, blob[:0x20])

    def self_status(self):
        """This game's player status (stats, level, equipment): g_Status's two ranges."""
        return b"".join(self.adapter.read_bytes(a, n) for a, n in STATUS_RANGES)

    def write_partner_status(self, blob):
        """The partner's status, for its body (module/partner.c); magic last."""
        if len(blob) != sum(n for _, n in STATUS_RANGES):
            return
        self.adapter.write_bytes(STATUS_PARTNER + 4, blob)
        self.adapter.write_bytes(STATUS_PARTNER, struct.pack("<I", STATUS_MAGIC))

    def write_partner(self, presence):
        self.adapter.write_bytes(self.address + PARTNER, presence.pack())
        self.adapter.write_bytes(self.address + PARTNER_PAD, struct.pack("<I", presence.pad))
        self.adapter.write_bytes(self.address + PARTNER_AGE, struct.pack("<I", 0))

    # --- event rings (module/link.h). Each event is its raw 8 bytes: the host only relays them.

    def _ring(self, offset):
        return struct.unpack("<II", self.adapter.read_bytes(self.address + offset, 8))

    def take_events(self):
        """Everything the game wrote to its out ring since last time, as raw 8-byte events."""
        head, tail = self._ring(OUT_RING)
        out = []
        while tail != head:
            slot = self.address + OUT_RING + 8 + (tail % RING_SIZE) * EVENT_SIZE
            out.append(self.adapter.read_bytes(slot, EVENT_SIZE))
            tail = (tail + 1) & 0xFFFFFFFF
        self.adapter.write_bytes(self.address + OUT_RING + 4, struct.pack("<I", tail))
        return out

    def give_events(self, events):
        """Writes as many events as fit into the game's in ring; returns how many."""
        head, tail = self._ring(IN_RING)
        n = 0
        for ev in events:
            if head - tail >= RING_SIZE:
                break
            slot = self.address + IN_RING + 8 + (head % RING_SIZE) * EVENT_SIZE
            self.adapter.write_bytes(slot, ev)
            head = (head + 1) & 0xFFFFFFFF
            n += 1
        self.adapter.write_bytes(self.address + IN_RING, struct.pack("<I", head))
        return n

    def dropped(self):
        return struct.unpack("<I", self.adapter.read_bytes(self.address + DROPPED, 4))[0]

    # --- commands (host -> game) and saves (module/link.h, design/M3)

    def command(self, type, stage=0, room_id=0, x=0, y=0):
        """Issues a command; returns its seq. The game sets cmdDone = seq when it's done."""
        seq = struct.unpack("<I", self.adapter.read_bytes(self.address + CMD, 4))[0] + 1
        self.adapter.write_bytes(self.address + CMD, _COMMAND.pack(seq, type, stage, room_id, x, y, 0))
        return seq

    def command_done(self):
        return struct.unpack("<I", self.adapter.read_bytes(self.address + CMD_DONE, 4))[0]

    def save_seq(self):
        return struct.unpack("<I", self.adapter.read_bytes(self.address + SAVE_SEQ, 4))[0]

    def save_out(self):
        return self.adapter.read_bytes(self.address + SAVE_OUT, SAVE_DATA_SIZE)

    def put_save(self, blob):
        assert len(blob) == SAVE_DATA_SIZE
        self.adapter.write_bytes(self.address + SAVE_IN, blob)

    def save_block(self):
        return struct.unpack("<I", self.adapter.read_bytes(self.address + SAVE_BLOCK, 4))[0]

    def card_result(self):
        return struct.unpack("<I", self.adapter.read_bytes(self.address + CARD_RESULT, 4))[0]

    # --- shared rooms (design/M4)

    def set_control(self, bits):
        self.adapter.write_bytes(self.address + CONTROL, struct.pack("<I", bits))

    def control(self):
        return struct.unpack("<I", self.adapter.read_bytes(self.address + CONTROL, 4))[0]

    # --- characters and per-player settings (design/M8, M8b)

    def set_character(self, character):
        """CHAR_*: the character this game's player plays, from the game's next load."""
        self.adapter.write_bytes(self.address + CHARACTER, struct.pack("<I", character))

    def set_options(self, bits):
        self.adapter.write_bytes(self.address + OPTIONS, struct.pack("<I", bits))

    def set_pad_extra(self, bits):
        self.adapter.write_bytes(self.address + PAD_EXTRA, struct.pack("<I", bits))

    def set_rank(self, rank):
        self.adapter.write_bytes(self.address + RANK, struct.pack("<I", rank))

    def snapshot_out(self):
        """(seq, bytes) of this game's latest room snapshot (it's the authority)."""
        seq, size = struct.unpack("<II", self.adapter.read_bytes(self.address + SNAP_OUT_SEQ, 8))
        return seq, self.adapter.read_bytes(self.address + SNAP_OUT, min(size, SNAP_MAX)) if seq else b""

    def snapshot_in_seq(self):
        return struct.unpack("<I", self.adapter.read_bytes(self.address + SNAP_IN_SEQ, 4))[0]

    def put_snapshot(self, data):
        seq, _ = struct.unpack("<II", self.adapter.read_bytes(self.address + SNAP_IN_SEQ, 8))
        self.adapter.write_bytes(self.address + SNAP_IN, data[:SNAP_MAX])
        self.adapter.write_bytes(self.address + SNAP_IN_SEQ, struct.pack("<II", seq + 1, len(data)))

