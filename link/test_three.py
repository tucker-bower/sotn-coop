"""Three games linked in pairs (M17 step 3, 3+ players): the real hosts, transports and mailboxes on
localhost, with no games (the mailboxes are plain memory: test_malformed's Memory).

    python link/test_three.py

Each game has a host per partner, each with its own view of the game's mailbox (mailbox.Partners).
- Every game sees both others: each one's presence lands in its own partner slot.
- An event a game queues reaches both others, once each.
- Sprites and a weapon copy land in the right partner's fields and copies, and nowhere else.
All of it twice: with every pair linked, and with games 1 and 2 unable to reach each other, so
they go through game 0 (link/mesh.py, design criterion 2)."""

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from link import transport as tr  # noqa: E402
from link.host import Host  # noqa: E402
from link.mesh import Mesh  # noqa: E402
from link.mailbox import (IN_RING, OUT_RING, RING_SIZE, SELF, SELF_SPRITES, SPRITE_SIZE, WEAPON_HAND_SIZE,  # noqa: E402
                          WEAPON_MAGIC, WEAPON_SELF, WEAPON_SIZE, Mailbox, Partners, Presence, weapon_partner)
from test_malformed import MAILBOX, Memory  # noqa: E402


class Game:
    def __init__(self, n, clock):
        self.n = n
        self.memory = Memory()
        self.mailbox = Mailbox(self.memory, MAILBOX)
        self.partners = Partners(self.mailbox)
        self.hosts = {}  # the other game's number -> (host, transport)
        self.clock = clock
        self.mesh = Mesh(n)

    def link(self, other, k):
        t = tr.UdpTransport()
        t.clock = self.clock
        self.mesh.add(other, t)
        self.hosts[other] = (Host(self.partners.view(k), t, rank=self.n), t)
        return t

    def relay(self, other, k):
        t = self.mesh.relay(other)
        self.hosts[other] = (Host(self.partners.view(k), t, rank=self.n), t)

    def frame(self):
        for host, _ in self.hosts.values():
            host.after_frame()


def main():
    failures = []
    for direct in (True, False):
        print("every pair linked" if direct else "games 1 and 2 through game 0")
        three(direct, failures)
    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


def three(direct, failures):
    def check(ok, what):
        print(("ok   " if ok else "FAIL ") + what)
        if not ok:
            failures.append(what)

    now = [0.0]
    games = [Game(n, lambda: now[0]) for n in range(3)]
    slot = {}  # (game, other) -> the partner slot game keeps other in
    for g in games:
        for k, other in enumerate(o for o in range(3) if o != g.n):
            slot[g.n, other] = k
    for a in range(3):
        for b in range(a + 1, 3):
            if direct or a == 0:
                ta, tb = games[a].link(b, slot[a, b]), games[b].link(a, slot[b, a])
                ta.connect(tb.port)
                tb.connect(ta.port)
    if not direct:
        games[1].relay(2, slot[1, 2])
        games[2].relay(1, slot[2, 1])

    def frames(n=1):
        for _ in range(n):
            now[0] += 1 / 60
            for g in games:
                g.frame()

    for g in games:  # each game somewhere of its own: x = 100 + its number
        g.memory.write_bytes(MAILBOX + SELF, Presence(flags=1, stage=1, x=100 + g.n, y=50).pack())
    frames(10)
    check(all(h.partner_hello for g in games for h, _ in g.hosts.values()), "three hosts shake hands in pairs")
    seen = {(g.n, o): g.mailbox.partner_presence(slot[g.n, o]).x for g in games for o in g.hosts}
    check(all(x == 100 + o for (_, o), x in seen.items()), f"each game sees both others, each in its own slot: {seen}")

    # an event: game 0 finds something (kind 5, value 77)
    heads = [struct.unpack("<I", g.memory.read_bytes(MAILBOX + IN_RING, 4))[0] for g in games]
    m = games[0].memory
    head = struct.unpack("<I", m.read_bytes(MAILBOX + OUT_RING, 4))[0]
    m.write_bytes(MAILBOX + OUT_RING + 8 + (head % RING_SIZE) * 8, struct.pack("<BxHI", 5, 0, 77))
    m.write_bytes(MAILBOX + OUT_RING, struct.pack("<I", head + 1))
    frames(20)

    def got(g, since):
        head = struct.unpack("<I", g.memory.read_bytes(MAILBOX + IN_RING, 4))[0]
        return [struct.unpack("<BxHI", g.memory.read_bytes(MAILBOX + IN_RING + 8 + (i % RING_SIZE) * 8, 8))[2]
                for i in range(since, head)]
    check(got(games[1], heads[1]) == [77] and got(games[2], heads[2]) == [77] and got(games[0], heads[0]) == [],
          "an event reaches both others, once each, and not its own game")

    # sprites: game 2 draws three; game 0 keeps it in slot 1, game 1 in slot 1 too
    g2 = games[2].memory
    g2.write_bytes(MAILBOX + SELF_SPRITES, struct.pack("<I", 3))
    g2.write_bytes(MAILBOX + SELF_SPRITES + 4, bytes([0xAB]) * 3 * SPRITE_SIZE)
    frames(5)
    counts = {(g.n, k): g.mailbox.partner_sprite_count(k) for g in games[:2] for k in range(2)}
    check(counts == {(0, slot[0, 2]): 3, (0, slot[0, 1]): 0, (1, slot[1, 2]): 3, (1, slot[1, 0]): 0},
          f"game 2's sprites are in its slot in each game, and only there: {counts}")

    # a weapon: game 1 loads a sword into hand 1
    blob = struct.pack("<III", WEAPON_MAGIC, 1, 0x10) + bytes(0x14) + bytes([0xCD]) * (WEAPON_SIZE - 0x20)
    games[1].memory.write_bytes(WEAPON_SELF + WEAPON_HAND_SIZE, blob)
    frames(30)
    for g in (games[0], games[2]):
        k = slot[g.n, 1]
        here = g.memory.read_bytes(weapon_partner(k, 1), WEAPON_SIZE)
        other = g.memory.read_bytes(weapon_partner(1 - k, 1), 0x20)
        check(here == blob and other == bytes(0x20),
              f"game {g.n} has game 1's sword at partner {k}'s copy ({weapon_partner(k, 1):#x}), not partner {1 - k}'s")
    if not direct:
        check(games[0].mesh.forwarded > 100, f"game 0 passed {games[0].mesh.forwarded} datagrams between 1 and 2")


if __name__ == "__main__":
    sys.exit(main())
