"""Events to a partner who isn't there (issue 223): the real hosts and transports, two of them on
localhost with no games, on a made-up clock.

    python link/test_backlog.py

- The partner leaves and the host plays on for ten minutes, finding something every second: what
  it sends a second stays flat (it used to resend the whole growing backlog, several times a second).
- A solo castle (no partner at all) keeps no events.
- A partner back after an outage, short or long, gets every event once, in order."""

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from link.mailbox import IN_RING, OUT_RING, RING_SIZE  # noqa: E402
from test_malformed import MAILBOX, Player  # noqa: E402

FPS = 60


def put_event(p, value):
    """The game queues an event (a find): kind 5, its value."""
    head = struct.unpack("<I", p.memory.read_bytes(MAILBOX + OUT_RING, 4))[0]
    p.memory.write_bytes(MAILBOX + OUT_RING + 8 + (head % RING_SIZE) * 8, struct.pack("<BxHI", 5, 0, value))
    p.memory.write_bytes(MAILBOX + OUT_RING, struct.pack("<I", head + 1))


def received(p, since):
    """The event values the game has been given since its in ring's head was `since`."""
    head = struct.unpack("<I", p.memory.read_bytes(MAILBOX + IN_RING, 4))[0]
    return [struct.unpack("<BxHI", p.memory.read_bytes(MAILBOX + IN_RING + 8 + (i % RING_SIZE) * 8, 8))[2]
            for i in range(since, head)], head


def in_head(p):
    return struct.unpack("<I", p.memory.read_bytes(MAILBOX + IN_RING, 4))[0]


def main():
    failures = []

    def check(ok, what):
        print(("ok   " if ok else "FAIL ") + what)
        if not ok:
            failures.append(what)

    now = [0.0]
    clock = lambda: now[0]  # noqa: E731

    def frames(players, n):
        for _ in range(n):
            now[0] += 1 / FPS
            for p in players:
                p.host.after_frame()

    # 1. The partner leaves; the host plays on for ten minutes, a find every second
    a, b = Player(0, clock), Player(1, clock)
    a.t.connect(b.t.port)
    b.t.connect(a.t.port)
    frames((a, b), 30)
    check(a.host.partner_hello and b.host.partner_hello, "two hosts shake hands")
    b.t.close()  # gone: its app closed without a word
    per_minute = []
    for minute in range(10):
        sent = a.t.bytes_sent
        for s in range(60):
            put_event(a, minute * 60 + s)
            frames((a,), FPS)
        per_minute.append(a.t.bytes_sent - sent)
    check(per_minute[-1] <= per_minute[0] * 1.1,
          f"ten minutes after the partner left, what's sent a minute stays flat: {per_minute[0]} bytes in the "
          f"first minute, {per_minute[-1]} in the tenth")
    check(len(a.host.events.unacked) == 600, f"the finds are kept for the partner's return ({len(a.host.events.unacked)})")
    a.t.close()

    # 2. A solo castle: no partner at all
    solo = Player(0, clock)
    for s in range(300):
        put_event(solo, s)
        frames((solo,), 12)
    check(not solo.host.events.unacked, f"solo: no events are kept ({len(solo.host.events.unacked)})")
    solo.t.close()

    # 3. Outages, short and long (the partner's sid stays the same): every event once, in order
    a, b = Player(0, clock), Player(1, clock)
    a.t.connect(b.t.port)
    b.t.connect(a.t.port)
    frames((a, b), 30)
    head, value = in_head(b), 1000
    for seconds in (1, 5, 30):
        sent = []
        a.t.partitioned = b.t.partitioned = True
        for _ in range(seconds * 2):
            put_event(a, value)
            sent.append(value)
            value += 1
            frames((a, b), FPS // 2)
        a.t.partitioned = b.t.partitioned = False
        frames((a, b), FPS)
        got, head = received(b, head)
        check(got == sent, f"after {seconds} s cut off: the partner got all {len(sent)} events once, in order "
                           f"(got {len(got)})")
    check(not a.host.events.unacked, "and nothing is left unacked")
    a.t.close()
    b.t.close()

    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
