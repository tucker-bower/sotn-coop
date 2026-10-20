"""M3b acceptance tests: the game's own save rooms, end to end (design/M3b-save-rooms.md).

A saves in a real save room: walk into the coffin, press Up. The coffin heals A, and the game's
own memory card dialog saves. B's game then writes its own card save for the same room."""

import tempfile
from pathlib import Path

from session import Session, SessionRun, session_scenario  # first: puts `link` on the path

from link.jointsave import read_session, save_room
from link.mailbox import BUSY, CARD_OK, IN_PLAY
from module import COOP_DISC
from session_progress import arrive, status

NZ0 = 0x0C
SAVE_ROOM = 200       # NZ0 room (16,35): a save room
COFFIN = (128, 0xA4)  # where a save-room load puts the player, in the coffin
TITLE_TO_LOAD = [(600, ""), (2, "start"), (360, ""), (2, "cross"), (300, ""), (2, "cross")]  # from the title


def save_in_coffin(run, s, saver, partner, path):
    """saver saves in the real coffin. Returns (frames from the saver's save to the partner's
    card write, frames the partner was frozen)."""
    arrive(run, saver, NZ0, SAVE_ROOM, *COFFIN)
    run.step(60)
    run.step(2, p1=("up", "") if saver is s.a else ("", "up"))
    for _ in range(600):  # the coffin closes, then the game's dialog saves
        run.step(1)
        if saver.mailbox("save_seq"):
            break
    frozen = 0
    for i in range(600):
        t = partner.read("g_Timer")
        run.step(1)
        frozen += partner.read("g_Timer") == t
        if partner.mailbox("card_result"):
            break
    for _ in range(60):
        run.step(1)
        if path.exists():
            break
    return i, frozen


def save_and_check(run):
    """A saves in the coffin, in its own session; checks M3b criterion 1. Returns
    (card images, statuses) at the save, for the resume test."""
    path = Path(tempfile.mkdtemp(prefix="coop-saveroom-")) / "session.coop"
    with Session(COOP_DISC, starts=("nz0", "entrance"), session_file=path) as s:
        sub = SessionRun(s, run.name)
        a, b = s.a, s.b
        a.write("g_Status", 10, "<i", 0x23C)  # so the coffin's heal shows
        hp_b = status(b)["hp"]
        frames, frozen = save_in_coffin(sub, s, a, b, path)
        run.expect(status(a)["hp"] == status(a)["hp_max"], "the coffin healed A", hp=status(a)["hp"])
        run.expect(status(b)["hp"] == hp_b, "B's HP is unchanged (the heal is A's only)", hp=status(b)["hp"], was=hp_b)
        run.expect(a.mailbox("save_seq") >= 1 and any(a.card()), "A saved to its card through the game's dialog")
        run.expect(b.mailbox("card_result") == CARD_OK, "B's game wrote its own card save", result=b.mailbox("card_result"))
        run.expect(b.mailbox("save_block") == a.mailbox("save_block"), "in the same block",
                   a=a.mailbox("save_block"), b=b.mailbox("save_block"))
        run.expect(frames < 300 and 0 < frozen < 120, "B's save was done within 5 s of A's, frozen under 2 s",
                   frames=frames, frozen=frozen)
        run.expect(path.exists(), "the session file (backup) was written too")
        blobs = read_session(path)
        run.expect(save_room(blobs[0]) == save_room(blobs[1]), "both saves resume in A's save room",
                   a=save_room(blobs[0]), b=save_room(blobs[1]))
        sub.step(60)
        run.expect(b.snapshot()["game_state"] == 2, "B carries on playing")
        return (a.card(), b.card()), (status(a), status(b))


def boot_and_load(g):
    """From power-on: title -> File select -> the first save."""
    for _ in range(6000):  # boot: how long depends on the BIOS
        if g.read("g_GameState") == 1:
            break
        g.step(1)
    for n, pad in TITLE_TO_LOAD:
        for _ in range(n):
            g.step(1, pad)


@session_scenario(starts=("nz0", "entrance"))
def save_room_real(run):
    """M3b criterion 1: A saves in the coffin. A's card and B's card both hold a save for that
    save room, in the same block, each with its own status. B was frozen only while writing.
    The coffin healed A only."""
    save_and_check(run)


@session_scenario(starts=(None, None))
def resume_from_load_menu(run):
    """M3b criterion 2: both games boot fresh with those memory cards; each player goes title ->
    File select -> the save. Both are in play in the save room with their saved status, and the
    shared flags, map and gold are identical."""
    cards, saved = save_and_check(run)
    a, b = run.s.a, run.s.b
    a.load_card(cards[0])
    b.load_card(cards[1])
    boot_and_load(a)
    boot_and_load(b)
    ok = False
    for i in range(1200):
        run.step(1)
        pa, pb = a.mailbox("self_presence"), b.mailbox("self_presence")
        if pa.flags & IN_PLAY and pb.flags & IN_PLAY and not (pa.flags | pb.flags) & BUSY:
            ok = True
            break
    run.expect(ok, "both games loaded their saves and are in play", frames=i)
    run.expect(pa.stage == pb.stage == NZ0 and pa.room_id == pb.room_id == SAVE_ROOM, "both in the save room",
               a=str(pa.room), b=str(pb.room))
    for who, g, st in (("A", a, saved[0]), ("B", b, saved[1])):
        now = status(g)
        run.expect(all(now[k] == st[k] for k in ("level", "hp_max", "hand", "body", "relics")),
                   f"{who} has its own saved status")
    run.step(30)
    from session_scenarios import assert_converged
    assert_converged(run)


@session_scenario(starts=("nz0", "entrance"))
def save_room_partner_no_card(run):
    """M3b criterion 3: B's card is unformatted (all zero). A saves in the coffin: B's card write
    fails cleanly, B's save still reaches session.coop, and B isn't left frozen."""
    path = Path(tempfile.mkdtemp(prefix="coop-saveroom-")) / "session.coop"
    with Session(COOP_DISC, starts=("nz0", "entrance"), session_file=path) as s:
        sub = SessionRun(s, run.name)
        a, b = s.a, s.b
        b.load_card(bytes(len(b.card())))
        save_in_coffin(sub, s, a, b, path)
        run.expect(b.mailbox("card_result") not in (0, CARD_OK), "B's card write reported a failure",
                   result=b.mailbox("card_result"))
        run.expect(path.exists() and len(read_session(path)) == 2, "B's save still reached session.coop")
        t = b.read("g_Timer")
        sub.step(60)
        run.expect(b.read("g_Timer") > t and b.snapshot()["game_state"] == 2, "B isn't frozen")
