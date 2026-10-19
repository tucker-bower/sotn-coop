"""The game <-> host mailbox in RAM. Mirrors module/link.h: keep the two in sync."""

import struct
from dataclasses import astuple, dataclass

COOP_MAGIC = 0x504F4F43  # 'COOP'
LINK_VERSION = 5

IN_PLAY, SPRITE, PAUSED, BUSY, DEAD = 1, 2, 4, 8, 16  # CoopPresence.flags

_PRESENCE = struct.Struct("<BBBBHHhhhhhHHHIHhhH")  # CoopPresence, 0x24 bytes
_HEADER = struct.Struct("<III")                # magic, version, heartbeat
SELF, PARTNER = 0x0C, 0x30                     # offsets in CoopLink
PARTNER_AGE = 0x54
OUT_RING, IN_RING, DROPPED = 0x58, 0x860, 0x1068
CMD, CMD_DONE, SAVE_SEQ, SAVE_OUT, SAVE_IN = 0x106C, 0x107C, 0x1080, 0x1084, 0x2250
SAVE_BLOCK, CARD_RESULT = 0x341C, 0x3420
CARD_OK = 6  # the save room's card state machine: 6 = saved, 7-11 = card errors
SAVE_DATA_SIZE = 0x11CC
CMD_ARRIVE, CMD_LOAD_SAVE, CMD_SAVE_NOW, CMD_GAME_OVER = 1, 2, 3, 4
_COMMAND = struct.Struct("<IHHHhhH")
RING_SIZE, EVENT_SIZE = 256, 8                 # CoopRing: u32 head, u32 tail, CoopEvent[256]
EV_FLAG, EV_MAP, EV_ITEM, EV_GRANT, EV_GOLD = 1, 2, 3, 4, 5


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
    pad: int = 0

    SIZE = _PRESENCE.size

    def pack(self):
        return _PRESENCE.pack(*astuple(self))

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

    def header(self):
        return _HEADER.unpack(self.adapter.read_bytes(self.address, _HEADER.size))

    def ready(self):
        magic, version, _ = self.header()
        return magic == COOP_MAGIC and version == LINK_VERSION

    def heartbeat(self):
        return self.header()[2]

    def self_presence(self):
        return Presence.unpack(self.adapter.read_bytes(self.address + SELF, Presence.SIZE))

    def partner_presence(self):
        return Presence.unpack(self.adapter.read_bytes(self.address + PARTNER, Presence.SIZE))

    def partner_age(self):
        return struct.unpack("<I", self.adapter.read_bytes(self.address + PARTNER_AGE, 4))[0]

    def write_partner(self, presence):
        self.adapter.write_bytes(self.address + PARTNER, presence.pack())
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

