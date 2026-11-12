"""The endings, played through: the boss falls, both games play the ending to its end and are back at
the title, for each pairing of characters. The boss tests (session_m12's boss_flow) stop where the
ending starts; a playtester found that not every ending finishes."""

import os

from session import session_scenario  # first: puts `link` on the path

from session_m12 import GAME_ENDING, STARTS, boss_flow

GAME_INIT, GAME_TITLE = 0, 1
ENDING_KIND = 0x800978B4  # D_800978B4: which ending the game plays
THROUGH = 60000  # frames for the ending, the staff roll and back to the title (some 20 minutes of play)


def play_through(run, limit=THROUGH):
    """Run both games until each has left its ending for the title (Game_Init or Game_Title after
    Game_Ending). Returns each game's frame, or None; logs where each was every 3000 frames."""
    a, b = run.s.a, run.s.b
    done, seen, log = [None, None], [False, False], []
    for t in range(limit):
        for k, g in enumerate((a, b)):
            s = g.read("g_GameState")
            seen[k] = seen[k] or s == GAME_ENDING
            if done[k] is None and seen[k] and s in (GAME_INIT, GAME_TITLE):
                done[k] = t
        if None not in done:
            break
        if os.environ.get("ENDING_DEBUG") and t % 150 == 0 and t < 9000:
            print(t, [(g.read("g_GameState"), g.read("g_GameStep"), g.read(0x8013901C, "<h"), g.read(0x8013B61C, "<i"),
                       g.read(0x801396F4, "<i"), g.read(0x8013AE80, "<i"), g.read(0x80139A68, "<i"), g.read(0x80139A70, "<i"),
                       g.read("g_CdStep"), g.read("g_IsUsingCd")) for g in (a, b)], flush=True)
        if t % 3000 == 0:
            log.append((t, [(g.read("g_GameState"), g.read("g_GameStep"), g.read("g_MenuStep")) for g in (a, b)]))
            if os.environ.get("ENDING_DEBUG"):
                print(log[-1], flush=True)
                run.capture()
        # press nothing: an ending plays out on its own (a prompt that needs a press is checked below)
        run.step(1)
    return done, seen, log


def _ending_test(boss, start, characters, full):
    name = boss.lower()
    pair = " and ".join(("alucard", "richter", "maria")[c] for c in characters).replace(" ", "_")

    def test(run):
        import bossstarts
        boss_flow(run, next(r for r in bossstarts.B if r["name"] == boss))
        kinds = [g.read(ENDING_KIND) for g in (run.s.a, run.s.b)]
        done, seen, log = play_through(run)
        run.capture()
        run.expect(all(seen), "both games are in the ending", seen=seen, kinds=kinds)
        run.expect(None not in done, "both play it through and are back at the title", done=done, log=log[-6:],
                   kinds=kinds, end=[(g.read("g_GameState"), g.read("g_GameStep")) for g in (run.s.a, run.s.b)])

    test.__name__ = f"ending_{name}_{pair}"
    test.__doc__ = f"{boss} falls with {pair.replace('_', ' ')} fighting; both games play the ending to the title."
    session_scenario(starts=(start,) * 2, characters=characters, full=full)(test)


DRACULA = str(STARTS / "Boss - Dracula.state")
RICHTER = str(STARTS / "Boss - Richter.state")
for _c, _full in (((0, 0), False), ((0, 1), False), ((1, 2), False), ((2, 2), True), ((1, 1), True)):
    _ending_test("Dracula", DRACULA, _c, _full)
    _ending_test("Richter", RICHTER, _c, _full)
