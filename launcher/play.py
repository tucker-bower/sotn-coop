"""Dev presets: both games started where a particular test happens (PRESETS below), in the
same window and frame loop players get (gameview.py). Players use app.py.

    python launcher/play.py --preset hall

Memory cards persist in cards/ and the joint save goes to cards/session.coop (next to the .bat
files of a dev install: scripts/install_launcher.sh).
"""

import argparse
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
for sub in ("launcher", "harness", ""):
    sys.path.insert(0, str(APP / sub) if sub else str(APP))

import pygame  # noqa: E402

from gameview import SCALE, BAR, H, W, Audio, GameView, Pads  # noqa: E402
from link.mailbox import CMD_ARRIVE  # noqa: E402
from module import COOP_DISC  # noqa: E402
from session import Session  # noqa: E402

NZ0 = 0x0C
SAVE_ROOM = 200
NO0, NO1 = 0x00, 0x01
NEXT_TO_DOPPLEGANGER = (96, 40, 135)  # NO1 room 96: walk left into the Doppleganger's room
LEFT_OF_MARIA = (80, 728, 135)        # NO0 room 80: walk right into the first Maria scene
CARDS = APP.parent / "cards"  # next to the .bat files

# name: (start A, start B, what to try, setup(session)). Starts are savestate names, or None for
# power-on (title screen).
PRESETS = {
    "hall": ("entrance", "entrance",
             "SHARED ROOM: walk left into the hall together and fight. Same enemies on both screens? "
             "Both can hit them? Enemies go for whoever is closer?", None),
    "teleport": ("nz0", "entrance",
                 "TELEPORT: right player presses SELECT (map), then X (cross) to jump to the left player. "
                 "Try both ways, and dying near the zombies (you should reappear by your partner).", None),
    "saveroom": ("nz0", "nz0",
                 "SAVE ROOM: left player is in a save room; step into the coffin and press UP. The right "
                 "game freezes briefly. Then quit (ESC) and run the RESUME preset.", "saveroom"),
    "resume": (None, None,
               "RESUME: both games boot to the title. In each: START, then X on File Select, then X on "
               "the save. You should both start in the save room.", None),
    "newgame": (None, None,
                "NEW GAME from the title in both games (fresh cards: use --fresh-cards). The real thing.", None),
    "boss": ("no1", "entrance",
             "BOSS: left player walks LEFT into the Doppleganger's room. The right player should be pulled "
             "in. Fight it together: twice the HP, it goes after both of you. Let one player die: they stay "
             "down until the boss is beaten, then reappear.", "boss"),
    "cutscene": ("no0", "entrance",
                 "CUTSCENE: left player walks RIGHT (jump the step) into the room where you first meet Maria. "
                 "The right player should be pulled in and see the scene too.", "cutscene"),
    "explore": ("no0", "no1",
                "EXPLORE: apart in Marble Gallery / Outer Wall. Pick things up: does your partner get them? "
                "Check the map (SELECT) for your partner's marker.", None),
}

def setup(name, s):
    if name == "saveroom":
        s.a.mailbox("command", CMD_ARRIVE, NZ0, SAVE_ROOM, 48, 0xA4)  # by the coffin, not in it
    elif name == "boss":
        s.a.mailbox("command", CMD_ARRIVE, NO1, *NEXT_TO_DOPPLEGANGER)
    elif name == "cutscene":
        s.a.mailbox("command", CMD_ARRIVE, NO0, *LEFT_OF_MARIA)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="hall", choices=sorted(PRESETS))
    ap.add_argument("--fresh-cards", action="store_true", help="start both games with empty memory cards")
    ap.add_argument("--frames", type=int, default=0, help="quit after N frames (tests)")
    ap.add_argument("--shot", help="save a screenshot of the window at the end (tests)")
    ap.add_argument("--profile", action="store_true", help="print where each frame's time goes")
    ap.add_argument("--aggro", type=int, default=50,
                    help="a boss's chance (%%) to switch to the other player, every 3 s (D62)")
    args = ap.parse_args()
    start_a, start_b, goal, setup_name = PRESETS[args.preset]
    CARDS.mkdir(exist_ok=True)
    if args.fresh_cards:  # a new playthrough: no cards, no joint save
        for f in list(CARDS.glob("*.mcd")) + [CARDS / "session.coop"]:
            f.unlink(missing_ok=True)
    pygame.init()
    pygame.display.set_caption(f"SOTN Co-op playtest: {args.preset}")
    screen = pygame.display.set_mode((W * SCALE * 2 + 8, H * SCALE + BAR))
    try:
        audio = Audio()
    except Exception as exc:  # no sound device: play silent
        print("no audio:", exc)
        audio = None
    with Session(COOP_DISC, starts=(start_a, start_b), session_file=CARDS / "session.coop", audio=True) as s:
        for g, name in zip((s.a, s.b), "AB"):
            card = CARDS / f"{name}.mcd"
            if card.exists():
                g.load_card(card.read_bytes())
        if setup_name:
            setup(setup_name, s)
        view = GameView(s, screen, Pads(), audio, goal=goal, aggro=args.aggro,
                        save_cards=(CARDS / "A.mcd", CARDS / "B.mcd"), frames=args.frames, profile=args.profile)
        view.run()
        if args.shot:
            pygame.image.save(screen, args.shot)
    pygame.quit()


if __name__ == "__main__":
    main()
