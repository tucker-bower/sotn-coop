"""M7 acceptance tests: online PC co-op (design/M7-repo-and-online.md, D74).

Covers:
- zero-infra connect codes (10-char stateless endpoint codes, room codes, direct IP:port);
- version mismatch refusal (link version and patch CRC32) between OnlineSession instances;
- MTU-safe compressed snapshots (strict 1200-byte UDP packet cap + 2% packet loss);
- online joint saves and both-dead reload across two separate OnlineSession instances."""

import tempfile
from pathlib import Path

from session import OnlineSession, session_scenario  # first: puts `link` on the path

from bots import walker
from link.mailbox import BUSY, DEAD, IN_PLAY
from link.transport import WIRE_VERSION
from link.rendezvous import ConnectError, decode_endpoint, encode_endpoint, make_room_code, parse_connect_input
from module import COOP_DISC
from session_progress import status

NZ0 = 0x0C
SAVE_ROOM = 200
COFFIN = (128, 0xA4)


def step_pair(s0, s1, n=1, p0="", p1=""):
    for _ in range(n):
        s0.step(1, p0)
        s1.step(1, p1)


@session_scenario()
def online_connect_codes(run):
    """M7 criterion 4 (M7b): 10-char endpoint codes round-trip (ip, port) and reject typos; two
    separate OnlineSession instances find each other by room code (link/connect.py)."""
    for ip, port in (("127.0.0.1", 54321), ("192.168.1.42", 12345), ("203.0.113.9", 65535), ("10.0.0.1", 1)):
        code = encode_endpoint(ip, port)
        run.expect(len(code) == 12 and decode_endpoint(code) == (ip, port),
                   f"endpoint code {code} round-trips {ip}:{port}", code=code)
        kind, parsed = parse_connect_input(code)
        run.expect(kind == "endpoint" and parsed == (ip, port), "parse_connect_input recognizes 10-char code")

    # Typos and invalid inputs must raise ConnectError with plain words.
    good = encode_endpoint("192.168.1.42", 54321)
    from link.rendezvous import ALPHABET, _DECODE
    flipped = good[:-1] + ALPHABET[_DECODE[good[-1]] ^ 1]  # corrupts the checksum bits
    for bad in ("", "SHORT", "0000-0000-00", flipped, "999.999.999.999:1234", "127.0.0.1:99999"):
        try:
            parse_connect_input(bad)
            run.expect(False, f"rejected invalid input {bad!r}")
        except ConnectError as exc:
            run.expect(len(str(exc)) > 10, f"plain error for {bad!r}", msg=str(exc))

    # The Join box takes only a code from the clipboard, never the rest of it (2026-10-28)
    from link.rendezvous import find_connect_code
    for clip, want in (("BAT-7K2Q", "BAT-7K2Q"), ("bat7k2q", "bat7k2q"), (f"my code is {good}, see you", good),
                       ("Room code BAT-7K2Q: join me", "BAT-7K2Q"), ("host at 192.168.1.10:47811 now", "192.168.1.10:47811"),
                       ("Just playtested Thor hosted and pc joining and it worked.", ""), ("Fog lamp", ""),
                       ("Please look at the CATEGORY", ""), (flipped, ""), ("", "")):
        got = find_connect_code(clip)
        run.expect(got == want, f"the clipboard {clip[:30]!r} gives {want!r}", got=got)

    # Room codes: two single-game OnlineSessions find each other through the relay (a folder
    # here: link/connect.FileRelay) and hole-punch, as they would across the internet.
    from link.connect import FileRelay
    relay = FileRelay(tempfile.mkdtemp(prefix="coop-relay-"))
    with OnlineSession(COOP_DISC, start="entrance", rank=0, bind_host="127.0.0.1") as s0, \
         OnlineSession(COOP_DISC, start="entrance", rank=1, bind_host="127.0.0.1") as s1:
        room = make_room_code()
        kind, norm_room = parse_connect_input(room.lower().replace("-", ""))
        run.expect(kind == "room" and norm_room == room, "room code parsed", room=room)
        s0.local.host("start_connect", room, "host", relay=relay, stun_servers=(), resolve=False)
        s1.local.host("start_connect", room, "join", relay=relay, stun_servers=(), resolve=False)
        for i in range(600):
            step_pair(s0, s1, 1)
            c0, c1 = s0.local.host("connect_status"), s1.local.host("connect_status")
            if c0["state"] == c1["state"] == "connected":
                break
        run.expect(c0["state"] == c1["state"] == "connected", "both found each other by room code",
                   frames=i, host=c0["state"], join=c1["state"])
        step_pair(s0, s1, 65)
        st0, st1 = s0.local.host("status"), s1.local.host("status")
        run.expect(st0["partner_hello"] is not None and st1["partner_hello"] is not None,
                   "both OnlineSessions completed HELO handshake", st0=st0["partner_hello"])
        # real sockets: under a busy machine a packet can land a frame late, so wait for it as for
        # the connection (a fixed frame failed alone in the 2026-11-07 gate, 12 games at once)
        for i in range(300):
            if s0.local.mailbox("partner_age") == 0 and s1.local.mailbox("partner_age") == 0:
                break
            step_pair(s0, s1, 1)
        run.expect(s0.local.mailbox("partner_age") == 0 and s1.local.mailbox("partner_age") == 0,
                   "both OnlineSessions exchange live presence", frames=i)


@session_scenario()
def online_version_mismatch(run):
    """M7 criterion 5: two OnlineSessions with mismatched patch CRC32 or link version refuse each
    other with a clear message, relay nothing, and recover when versions match."""
    with OnlineSession(COOP_DISC, start="entrance", rank=0, bind_host="127.0.0.1", patch_crc=0x11111111) as s0, \
         OnlineSession(COOP_DISC, start="entrance", rank=1, bind_host="127.0.0.1", patch_crc=0x22222222) as s1:
        s0.connect(("127.0.0.1", s1.port))
        s1.connect(("127.0.0.1", s0.port))
        step_pair(s0, s1, 70)
        st0, st1 = s0.local.host("status"), s1.local.host("status")
        run.expect(st0["mismatch"] and "disc" in st0["mismatch"],
                   "host refuses partner with a different disc patch CRC", why=st0["mismatch"])
        run.expect(st1["mismatch"] and "disc" in st1["mismatch"],
                   "joiner also reports the disc patch mismatch", why=st1["mismatch"])

        # While refused, gold changes and presence are NOT relayed.
        gold0 = status(s1.local)["gold"]
        s0.local.write("g_Status", status(s0.local)["gold"] + 500, "<i", 0x28C)
        step_pair(s0, s1, 45)
        run.expect(status(s1.local)["gold"] == gold0, "no events relayed while refused")
        run.expect(s1.local.mailbox("partner_age") > 30, "no presence relayed while refused",
                   age=s1.local.mailbox("partner_age"))

        # Different link protocol version:
        s1.local.host("set_hello", patch_crc=0x11111111, link_version=WIRE_VERSION - 1)
        step_pair(s0, s1, 70)
        st0 = s0.local.host("status")
        run.expect(st0["mismatch"] and "version" in st0["mismatch"],
                   "refuses partner with different link protocol version", why=st0["mismatch"])

        # Matching versions lift the refusal and sync resumes:
        s1.local.host("set_hello", patch_crc=0x11111111, link_version=WIRE_VERSION)
        step_pair(s0, s1, 70)
        st0, st1 = s0.local.host("status"), s1.local.host("status")
        run.expect(st0["mismatch"] is None and st1["mismatch"] is None, "matching HELO lifts the refusal")
        run.expect(s0.local.mailbox("partner_age") == 0 and s1.local.mailbox("partner_age") == 0,
                   "presence relays again once versions match")


@session_scenario()
def online_solo_death_reloads(run):
    """Issue 240: a host's player dying with no partner (a solo castle, or one the partner left)
    reloads the castle's last save. The game's own Game Over went on to its title and file
    select, which mean nothing in a castle."""
    tmp = Path(tempfile.mkdtemp(prefix="coop-solo-death-"))
    path = tmp / "session.coop"
    with OnlineSession(COOP_DISC, start="nz0", rank=0, session_file=path, bind_host="127.0.0.1") as s:
        g = s.local
        s.step(30)
        g.mailbox("command", 1, NZ0, SAVE_ROOM, *COFFIN)  # into the Alchemy Lab's coffin room, and save
        for _ in range(300):
            s.step(1)
            p = g.mailbox("self_presence")
            if p.stage == NZ0 and p.room_id == SAVE_ROOM and p.flags & IN_PLAY and not p.flags & BUSY:
                break
        s.step(60)
        s.step(2, "up")
        for _ in range(900):
            s.step(1)
            if path.exists() and g.mailbox("card_result"):
                break
        run.expect(path.exists(), "alone, the save was written")
        from coop_env import savestate
        g.load_state_file(str(savestate(COOP_DISC, "entrance")))
        s.step(30)
        g.write("g_Status", 1, "<i", 0x23C)  # 1 HP
        walk = walker("left", attack_every=0)
        for i in range(4000):
            s.step(1, walk(g.snapshot(), i))
            if g.mailbox("self_presence").flags & DEAD:
                break
        run.expect(bool(g.mailbox("self_presence").flags & DEAD), "the player died", frames=i)
        reloaded, title = False, False
        for i in range(1800):
            s.step(1)
            title |= g.read("g_GameState") == 1  # Game_Title
            p = g.mailbox("self_presence")
            if i > 60 and p.stage == NZ0 and p.flags & IN_PLAY and not p.flags & (BUSY | DEAD):
                reloaded = True
                break
        run.expect(reloaded, "the castle's save loaded: back in the Alchemy Lab's save room", frames=i)
        run.expect(not title, "and the game's title never showed")


@session_scenario()
def online_partner_leaves(run):
    """Playtest 2026-10-25: closing one player's app must tell the other at once (BYE), not leave
    it waiting in silence. The launcher then says "Your partner left the game"."""
    with OnlineSession(COOP_DISC, start="entrance", rank=0, bind_host="127.0.0.1") as s0:
        s1 = OnlineSession(COOP_DISC, start="entrance", rank=1, bind_host="127.0.0.1",
                           peer=("127.0.0.1", s0.port)).__enter__()
        s0.connect(("127.0.0.1", s1.port))
        step_pair(s0, s1, 120)
        run.expect(s0.local.mailbox("partner_age") == 0 and not s0.local.host("status")["partner_left"],
                   "linked, partner present")
        s1.__exit__(None, None, None)  # the partner's app closes
        for i in range(30):
            s0.step(1)
            if s0.local.host("status")["partner_left"]:
                break
        run.expect(s0.local.host("status")["partner_left"], "told within half a second", frames=i)


@session_scenario()
def online_room_three_players_drop_in(run):
    """M17 step 6 (Tucker, 2026-11-18: drop-in joining): three of the app's online sessions on one
    room code. Two play; the third joins while they do and is seated as player 2; every game then
    hears both its partners, each in its own slot (link/mesh.py slot())."""
    import os
    from link.connect import FileRelay
    from link.mesh import slot
    os.environ["COOP_NO_PORTMAP"] = "1"
    relay = FileRelay(tempfile.mkdtemp(prefix="coop-relay-"))
    kw = dict(relay=relay, stun_servers=(), resolve=False)
    room = make_room_code()
    with OnlineSession(COOP_DISC, start="entrance", rank=0, bind_host="127.0.0.1") as s0, \
         OnlineSession(COOP_DISC, start="entrance", rank=1, bind_host="127.0.0.1") as s1, \
         OnlineSession(COOP_DISC, start="entrance", rank=2, bind_host="127.0.0.1") as s2:
        s0.start_room(room, True, **kw)
        s1.start_room(room, False, **kw)
        both = lambda: s0.room_status(False)["players"] == [0, 1]
        for i in range(900):
            step_pair(s0, s1, 1)
            if both() and s1.room_status(False)["me"] == 1:
                break
        run.expect(both(), "the first joiner is seated as player 1, while both play", players=s0.room_status(False))
        step_pair(s0, s1, 120)
        s2.start_room(room, False, **kw)  # drop in, mid-game
        sessions = (s0, s1, s2)
        for i in range(1800):
            for s in sessions:
                s.step(1)
            if all(len(s.room_status(False)["players"]) == 3 for s in sessions) and s2.room_status(False)["me"] == 2:
                fresh = [[s.local.mailbox("partner_age", k=k) for k in range(2)] for s in sessions]
                if all(a < 30 for row in fresh for a in row):
                    break
        run.expect(s2.room_status(False)["me"] == 2, "the late joiner is seated as player 2",
                   status=[s.room_status(False)["players"] for s in sessions])
        ages = {n: [s.local.mailbox("partner_age", k=slot(n, m)) for m in range(3) if m != n]
                for n, s in enumerate(sessions)}
        run.expect(all(a < 30 for v in ages.values() for a in v), "every game hears both its partners",
                   ages=ages, frames=i)
