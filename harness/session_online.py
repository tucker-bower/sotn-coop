"""M7 acceptance tests: online PC co-op (design/M7-repo-and-online.md, D74).

Covers:
- zero-infra connect codes (10-char stateless endpoint codes, 6-char room codes, direct IP:port);
- version mismatch refusal (link version and patch CRC32) between OnlineSession instances;
- MTU-safe compressed snapshots (strict 1200-byte UDP packet cap + 2% packet loss);
- online joint saves and both-dead reload across two separate OnlineSession instances."""

import tempfile
from pathlib import Path

from session import OnlineSession, session_scenario  # first: puts `link` on the path

from bots import walker
from link.jointsave import read_session, save_room
from link.mailbox import BUSY, CARD_OK, DEAD, IN_PLAY, LINK_VERSION, ROLE_AUTHORITY, ROLE_GUEST
from link.rendezvous import (ConnectError, RoomResponder, decode_endpoint, encode_endpoint,
                             make_room_code, parse_connect_input, resolve_room_code)
from module import COOP_DISC
from session_progress import arrive, status
from session_scenarios import assert_converged
from session_shared import into_hall, stage_entities

NZ0 = 0x0C
SAVE_ROOM = 200
COFFIN = (128, 0xA4)


def step_pair(s0, s1, n=1, p0="", p1=""):
    for _ in range(n):
        s0.step(1, p0)
        s1.step(1, p1)


@session_scenario()
def online_connect_codes(run):
    """M7 criterion 4: 10-char stateless endpoint codes round-trip (ip, port) and reject typos;
    6-char room codes and direct IP:port pair two separate OnlineSession instances."""
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

    # Room-code discovery + direct IP pairing between two single-game OnlineSession instances.
    with OnlineSession(COOP_DISC, start="entrance", rank=0, bind_host="127.0.0.1") as s0, \
         OnlineSession(COOP_DISC, start="entrance", rank=1, bind_host="127.0.0.1") as s1:
        room = make_room_code()
        kind, norm_room = parse_connect_input(room.lower().replace("-", ""))
        run.expect(kind == "room" and norm_room == room, "6-char room code parsed", room=room)
        resp = RoomResponder(room, ("127.0.0.1", s0.port), relay=False)
        try:
            found = resolve_room_code(room, ("127.0.0.1", s1.port), timeout=2.0, relay=False)
            run.expect(found == ("127.0.0.1", s0.port), "joiner resolved host endpoint from room code", found=found)
            run.expect(resp.joiner_endpoint == ("127.0.0.1", s1.port),
                       "host responder learned joiner endpoint", joiner=resp.joiner_endpoint)
            s0.connect(resp.joiner_endpoint)
            s1.connect(found)
        finally:
            resp.close()
        step_pair(s0, s1, 65)
        st0, st1 = s0.local.host("status"), s1.local.host("status")
        run.expect(st0["partner_hello"] is not None and st1["partner_hello"] is not None,
                   "both OnlineSessions completed HELO handshake", st0=st0["partner_hello"])
        run.expect(s0.local.mailbox("partner_age") == 0 and s1.local.mailbox("partner_age") == 0,
                   "both OnlineSessions exchange live presence")


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
        s1.local.host("set_hello", patch_crc=0x11111111, link_version=LINK_VERSION - 1)
        step_pair(s0, s1, 70)
        st0 = s0.local.host("status")
        run.expect(st0["mismatch"] and "version" in st0["mismatch"],
                   "refuses partner with different link protocol version", why=st0["mismatch"])

        # Matching versions lift the refusal and sync resumes:
        s1.local.host("set_hello", patch_crc=0x11111111, link_version=LINK_VERSION)
        step_pair(s0, s1, 70)
        st0, st1 = s0.local.host("status"), s1.local.host("status")
        run.expect(st0["mismatch"] is None and st1["mismatch"] is None, "matching HELO lifts the refusal")
        run.expect(s0.local.mailbox("partner_age") == 0 and s1.local.mailbox("partner_age") == 0,
                   "presence relays again once versions match")


@session_scenario()
def online_mtu_and_loss(run):
    """M7 criterion 3: with a strict 1200-byte UDP MTU limit (any packet > 1200 bytes is dropped)
    and 2% random packet loss, shared rooms, compressed chunked snapshots, enemy kills, and
    shared progression work smoothly."""
    a, b = run.s.a, run.s.b
    a.transport("set_wan", mtu=1200, loss=0.02, seed=101)
    b.transport("set_wan", mtu=1200, loss=0.02, seed=202)
    into_hall(run)
    run.step(30)
    roles = (a.mailbox("self_presence").role, b.mailbox("self_presence").role)
    run.expect(roles == (ROLE_AUTHORITY, ROLE_GUEST), "shared room established over 1200-byte MTU link", roles=roles)

    hp0 = {s: e[3] for s, e in stage_entities(a).items() if e[3] > 0}
    killed = set()
    bot = walker("left", attack_every=6)
    for i in range(900):
        run.step(1, p1=("", bot(b.snapshot(), i)))
        now = stage_entities(a)
        for s in hp0:
            if s not in now or now[s][3] <= 0:
                killed.add(s)
        if killed:
            break
    run.expect(bool(killed), "guest killed an enemy over the lossy MTU-capped link", frames=i, killed=sorted(killed))
    run.step(60)
    wa, wb = a.transport("wan_stats"), b.transport("wan_stats")
    run.expect(wa["mtu_drops"] == 0 and wb["mtu_drops"] == 0,
               "zero packets exceeded the 1200-byte MTU cap", a=wa, b=wb)
    run.expect(0 < wa["max_packet_sent"] <= 1200 and 0 < wb["max_packet_sent"] <= 1200,
               "largest UDP packet stayed <= 1200 bytes", a_max=wa["max_packet_sent"], b_max=wb["max_packet_sent"])
    run.expect(wa["loss_drops"] + wb["loss_drops"] > 0, "simulated packet loss occurred and was tolerated",
               dropped=wa["loss_drops"] + wb["loss_drops"])
    assert_converged(run)


@session_scenario()
def online_joint_save(run):
    """M7 criterion 6: two separate OnlineSession instances (each with its own memory card and
    its own session.coop file, linked only over UDP) save at a coffin and reload when both die."""
    tmp = Path(tempfile.mkdtemp(prefix="coop-online-save-"))
    path0, path1 = tmp / "pc0/session.coop", tmp / "pc1/session.coop"
    with OnlineSession(COOP_DISC, start="nz0", rank=0, session_file=path0, bind_host="127.0.0.1") as s0, \
         OnlineSession(COOP_DISC, start="entrance", rank=1, session_file=path1, bind_host="127.0.0.1") as s1:
        s0.connect(("127.0.0.1", s1.port))
        s1.connect(("127.0.0.1", s0.port))
        step_pair(s0, s1, 30)

        # Player 0 walks into the Alchemy Lab coffin and saves.
        s0.local.mailbox("command", 1, NZ0, SAVE_ROOM, *COFFIN)
        for _ in range(300):
            step_pair(s0, s1, 1)
            p = s0.local.mailbox("self_presence")
            if p.stage == NZ0 and p.room_id == SAVE_ROOM and p.flags & IN_PLAY and not p.flags & BUSY:
                break
        step_pair(s0, s1, 60)
        step_pair(s0, s1, 2, p0="up")
        for _ in range(900):
            step_pair(s0, s1, 1)
            if path0.exists() and path1.exists() and s1.local.mailbox("card_result"):
                break
        run.expect(path0.exists() and path1.exists(), "both PCs wrote session.coop over the network link")
        run.expect(path0.read_bytes() == path1.read_bytes(), "both PCs have byte-identical session.coop files")
        run.expect(s1.local.mailbox("card_result") == CARD_OK, "remote PC also wrote its memory card save")
        blobs = read_session(path0)
        run.expect(save_room(blobs[0]) == save_room(blobs[1]), "both saves resume in the coffin's save room")

        # Now both players die in identical entrance worlds: both PCs reload the online joint save.
        from coop_env import savestate
        ent = str(savestate(COOP_DISC, "entrance"))
        for s in (s0, s1):
            s.local.load_state_file(ent)
        step_pair(s0, s1, 30)
        for s in (s0, s1):
            s.local.write("g_Status", 1, "<i", 0x23C)
        b0, b1 = walker("left", attack_every=0), walker("left", attack_every=0)
        for i in range(4000):
            step_pair(s0, s1, 1, b0(s0.local.snapshot(), i), b1(s1.local.snapshot(), i))
            if s0.local.mailbox("self_presence").flags & DEAD and s1.local.mailbox("self_presence").flags & DEAD:
                break
        run.expect(bool(s0.local.mailbox("self_presence").flags & DEAD and s1.local.mailbox("self_presence").flags & DEAD),
                   "both players died", frames=i)
        reloaded = False
        for i in range(1500):
            step_pair(s0, s1, 1)
            p0, p1 = s0.local.mailbox("self_presence"), s1.local.mailbox("self_presence")
            if i > 240 and p0.stage == NZ0 and p1.stage == NZ0 and p0.flags & IN_PLAY and p1.flags & IN_PLAY and not (p0.flags | p1.flags) & (BUSY | DEAD):
                reloaded = True
                break
        run.expect(reloaded, "both PCs reloaded the joint save into the save room over UDP", frames=i)
