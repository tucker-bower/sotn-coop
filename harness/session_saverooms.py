"""M3b acceptance tests: the game's own save rooms, end to end (design/M3b-save-rooms.md).

A saves in a real save room: walk into the coffin, press Up. The coffin heals A, and the game's
own memory card dialog saves. B's game then writes its own card save for the same room."""

import tempfile
from pathlib import Path

from session import Session, SessionRun, session_scenario  # first: puts `link` on the path

from link.jointsave import read_session, save_room
from link.mailbox import CARD_OK
from module import COOP_DISC
from session_progress import arrive, status

NZ0 = 0x0C
SAVE_ROOM = 200       # NZ0 room (16,35): a save room
COFFIN = (128, 0xA4)  # where a save-room load puts the player, in the coffin


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


@session_scenario(starts=("nz0", "entrance"))
def save_room_real(run):
    """M3b criterion 1: A saves in the coffin. A's card and B's card both hold a save for that
    save room, in the same block, each with its own status. B was frozen only while writing.
    The coffin healed A only."""
    save_and_check(run)


