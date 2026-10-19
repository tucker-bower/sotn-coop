"""The game <-> host mailbox in RAM. Mirrors module/link.h: keep the two in sync."""

import struct
from dataclasses import astuple, dataclass

COOP_MAGIC = 0x504F4F43  # 'COOP'
LINK_VERSION = 2

IN_PLAY, SPRITE = 1, 2  # CoopPresence.flags

_PRESENCE = struct.Struct("<BBBBHHhhhhhHHHI")  # CoopPresence, 0x1C bytes
_HEADER = struct.Struct("<III")                # magic, version, heartbeat
SELF, PARTNER = 0x0C, 0x28                     # offsets in CoopLink
PARTNER_AGE = 0x44


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
