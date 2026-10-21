"""M8 session tests (design/M8-maria-and-richter.md): mixed teams in two linked games."""

from session import session_scenario  # first: puts `link` on the path

from bots import walker
from link.mailbox import (BUSY, CHAR_ALUCARD, CHAR_RICHTER, CMD_LOAD_SAVE, CMD_SAVE_NOW, IN_PLAY,
                          ROLE_AUTHORITY, ROLE_GUEST)
from session_shared import into_hall, roles, stage_entities
import savestates as route


def reload_game(run, g, limit=3000):
    """A joint save and its load in game g: how Continue brings in each player's character."""
    seq, p = g.mailbox("save_seq"), g.mailbox("self_presence")
    g.mailbox("command", CMD_SAVE_NOW, p.stage, 0, p.room_left, p.room_top)
    for _ in range(limit):
        run.step(1)
        if g.mailbox("save_seq") != seq:
            break
    g.mailbox("put_save", g.mailbox("save_out"))
    g.mailbox("command", CMD_LOAD_SAVE)
    for _ in range(600):
        run.step(1)
        if g.read("g_GameState") == route.GAME_NOW_LOADING:
            break
    for _ in range(limit):
        run.step(1)
        q = g.mailbox("self_presence")
        if g.read("g_GameState") == route.GAME_PLAY and q.flags & IN_PLAY and not q.flags & BUSY:
            return True
    return False


@session_scenario(characters=(CHAR_ALUCARD, CHAR_RICHTER))
def mixed_party_shared_room(run):
    """M8 criterion 3 (first part): Alucard (A) and Richter (B) share the entrance hall. B is the
    guest, sees A's enemies, and his whip hits count in A's world. Each draws the other (the
    clip, and the screenshots in the out folder)."""
    a, b = run.s.a, run.s.b
    run.expect(reload_game(run, b), "B loads as Richter")
    run.expect(b.mailbox("self_presence").character == CHAR_RICHTER and
               a.mailbox("self_presence").character == CHAR_ALUCARD, "A plays Alucard, B Richter")
    into_hall(run)
    run.expect(roles(run) == (ROLE_AUTHORITY, ROLE_GUEST), "they share the room: A authority, B guest",
               roles=roles(run))
    ea, eb = stage_entities(a), stage_entities(b)
    run.expect(set(eb) == set(ea), "B's world has exactly A's stage entities")
    hp0 = {s: e[3] for s, e in ea.items() if e[3] > 0}
    bot = walker("left", attack_every=30)  # his whip takes longer than Alucard's punch
    for i in range(1200):
        run.step(1, p1=("", bot(b.snapshot(), i)))
        now = stage_entities(a)
        if any(s in now and now[s][3] < hp for s, hp in hp0.items()) or any(s not in now for s in hp0):
            break
    now = stage_entities(a)
    hit = [s for s, hp in hp0.items() if s not in now or now[s][3] < hp]
    run.expect(hit, "Richter's whip hurts A's enemies (in A's world)", enemies=len(hp0))
