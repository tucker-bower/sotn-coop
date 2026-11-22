"""3 and 4 players finding each other from one room code (M17 step 3, D211): the real rooms, hosts,
connectors and transports on the virtual internet of link/natsim.py, with no games (the mailboxes
are plain memory: test_malformed's Memory).

    python link/test_room.py

- Player 0 makes the code; the others join it and are seated 1, 2, 3, each told who's in.
- Behind routers that let them, every guest pair then links directly.
- Guests whose routers can't reach each other (random ports both sides) go through player 0
  (design criterion 2), and still see each other.
Either way every game ends up seeing every other in the partner slot link/mesh.py's slot() gives."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from link.mailbox import SELF, Mailbox, Presence  # noqa: E402
from link.mesh import Room, slot  # noqa: E402
from link.natsim import CONE, SYMMETRIC_RANDOM, Internet, MemoryRelay, StunServer  # noqa: E402
from link.transport import UdpTransport  # noqa: E402
from test_malformed import MAILBOX, Memory  # noqa: E402

CODE = "BAT-7K2Q"


def room(kinds, seconds=60, pair_timeout=20, max_players=4, gone=None):
    """kinds: each player's router. gone: {player: second} when that one's app goes quiet. Returns
    the players as (memory, mailbox, room)."""
    net = Internet()
    stuns = [StunServer(net, 3478), StunServer(net, 19302)]
    relay = MemoryRelay()
    now = [0.0]

    def player(n, kind):
        router = net.router(kind)
        def new_transport():
            t = UdpTransport(sock=net.socket(router), bind_host="0.0.0.0")
            t.clock = lambda: now[0]
            return t
        memory = Memory()
        mailbox = Mailbox(memory, MAILBOX)
        memory.write_bytes(MAILBOX + SELF, Presence(flags=1, stage=1, x=100 + n, y=50).pack())
        return memory, mailbox, Room(mailbox, CODE, n == 0, new_transport, pair_timeout=pair_timeout, max_players=max_players,
                                     relay=relay, stun_servers=[s.addr for s in stuns], resolve=False,
                                     portmap=lambda port: None)

    players = [player(0, kinds[0])]
    for _ in range(int(seconds * 60)):
        now[0] += 1 / 60
        if len(players) < len(kinds) and now[0] > 2 * len(players):  # a joiner every two seconds
            players.append(player(len(players), kinds[len(players)]))
        for n, (_, _, r) in enumerate(players):
            if gone and n in gone and now[0] >= gone[n]:
                continue
            r.tick(game_running=r.me is not None and len(r.hosts) == len(kinds) - 1)
        for s in stuns:
            s.tick()
    return players


def main():
    failures = []

    def check(ok, what):
        print(("ok   " if ok else "FAIL ") + what)
        if not ok:
            failures.append(what)

    for kinds, relayed in (((CONE, CONE, CONE), False), ((CONE, CONE, CONE, CONE), False),
                           ((CONE, SYMMETRIC_RANDOM, SYMMETRIC_RANDOM), True),
                           ((CONE, SYMMETRIC_RANDOM, SYMMETRIC_RANDOM, CONE), True)):
        n = len(kinds)
        players = room(kinds)
        name = f"{n} players ({', '.join(kinds)})"
        seats = sorted(r.me for _, _, r in players if r.me is not None)
        check(seats == list(range(n)), f"{name}: seated {seats}")
        seen = {}
        for _, mailbox, r in players:
            if r.me is None:
                continue
            for other in range(n):
                if other != r.me:
                    seen[r.me, other] = mailbox.partner_presence(slot(r.me, other)).x
        check(len(seen) == n * (n - 1) and all(x == 100 + o for (_, o), x in seen.items()),
              f"{name}: every game sees every other in its slot ({sum(x == 100 + o for (_, o), x in seen.items())}"
              f" of {n * (n - 1)})")
        through = {r.me: r.relayed() for _, _, r in players if r.me}
        want = {1: [2], 2: [1]} if relayed else {}
        check({k: v for k, v in through.items() if v} == want,
              f"{name}: {'1 and 2 go through player 0' if relayed else 'every pair is direct'} ({through})")

    # D221: a castle for two (Max players 2) seats two; a third with the code isn't let in
    players = room((CONE, CONE, CONE), seconds=60, max_players=2)  # the grace, then FULL_WAIT_S
    seats = [r.me for _, _, r in players]
    check(seats[:2] == [0, 1] and seats[2] is None and not players[0][2].hosts.get(2),
          f"Max players 2: the third isn't seated ({seats})")
    third = players[2][2]._first.connector
    check(third.state == "failed" and "room is full" in (third.reason or ""),
          f"#332: the third hears the room is full, not a timeout ({third.state}: {third.reason})")

    # #339: a joiner seated in the lobby that goes quiet gives its seat back, and the next gets it
    players = room((CONE, CONE, CONE), seconds=60, max_players=2, gone={1: 3.0})
    seats = [r.me for _, _, r in players]
    check(seats[2] == 1 and sorted(players[0][2].players) == [0, 1],
          f"#339: a seat left silent in the lobby goes to the next joiner ({seats}, {players[0][2].players})")

    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
