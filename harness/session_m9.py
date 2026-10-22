"""M9 session tests (design/M9-android.md): the Android app's way of running a game (in this
process, no worker) plays online with a PC game, the same protocol both ways."""

import tempfile

from session import OnlineSession, session_scenario  # first: puts `link` on the path

from link.connect import FileRelay
from link.mailbox import CMD_ARRIVE, ROLE_AUTHORITY, ROLE_GUEST
from link.rendezvous import make_room_code
from module import COOP_DISC
from session_online import step_pair
from session_progress import arrive
from session_shared import HALL


@session_scenario()
def online_in_process(run):
    """A in-process (as on Android) hosts by room code; B, a PC worker game, joins. They connect,
    each sees the other, and they share a room (B the guest)."""
    relay = FileRelay(tempfile.mkdtemp(prefix="coop-relay-"))
    with OnlineSession(COOP_DISC, start="entrance", rank=0, bind_host="127.0.0.1", in_process=True) as s0, \
         OnlineSession(COOP_DISC, start="entrance", rank=1, bind_host="127.0.0.1") as s1:
        run.expect(s0.local.proc is None, "A runs in this process")
        room = make_room_code()
        s0.local.host("start_connect", room, "host", relay=relay, stun_servers=(), resolve=False)
        s1.local.host("start_connect", room, "join", relay=relay, stun_servers=(), resolve=False)
        for i in range(600):
            step_pair(s0, s1, 1)
            c0, c1 = s0.local.host("connect_status"), s1.local.host("connect_status")
            if c0["state"] == c1["state"] == "connected":
                break
        run.expect(c0["state"] == c1["state"] == "connected", "connected by room code", frames=i)
        a, b = s0.local, s1.local
        for i in range(600):
            step_pair(s0, s1, 1, p0="left")
            if a.snapshot()["room"] == HALL and i > 200:
                break
        step_pair(s0, s1, 120)
        p = a.mailbox("self_presence")
        b.mailbox("command", CMD_ARRIVE, p.stage, p.room_id, p.ground_x + 24, p.ground_y)
        for _ in range(400):
            step_pair(s0, s1, 1)
            if b.mailbox("self_presence").role == ROLE_GUEST:
                break
        roles = (a.mailbox("self_presence").role, b.mailbox("self_presence").role)
        run.expect(roles == (ROLE_AUTHORITY, ROLE_GUEST), "they share the room: in-process A runs it",
                   roles=roles)
        run.expect(a.mailbox("partner_presence").stage == b.mailbox("self_presence").stage,
                   "A sees B")


@session_scenario()
def online_direct_join(run):
    """The ip:port fallback (Help › Online troubleshooting): A hosts by room code, B types A's
    address instead. They connect (a host only refuses HELOs of another room)."""
    with OnlineSession(COOP_DISC, start="entrance", rank=0, bind_host="127.0.0.1") as s0, \
         OnlineSession(COOP_DISC, start="entrance", rank=1, bind_host="127.0.0.1") as s1:
        relay = FileRelay(tempfile.mkdtemp(prefix="coop-relay-"))
        s0.local.host("start_connect", make_room_code(), "host", relay=relay, stun_servers=(), resolve=False)
        s1.connect(("127.0.0.1", s0.port))
        for i in range(600):
            step_pair(s0, s1, 1)
            h0, h1 = s0.local.host("status"), s1.local.host("status")
            if s0.local.host("handshake_tick").get("partner_hello") and s1.local.host("handshake_tick").get("partner_hello"):
                break
        run.expect(s0.local.host("handshake_tick").get("partner_hello"), "the host heard the direct joiner", frames=i)
        run.expect(s1.local.host("handshake_tick").get("partner_hello"), "and the joiner heard the host")
