"""SOTN Co-op playtest launcher: two games, two pads, one window (D36; the start of M6).

    python launcher/play.py --preset hall

Each preset starts both games where a particular test happens (PRESETS below). Pads: the first
controller plays the left game, the second the right one; the keyboard works too (HELP).
Memory cards persist in cards/ and the joint save goes to cards/session.coop.
"""

import argparse
import sys
import textwrap
import threading
import time
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP / "harness"))
sys.path.insert(0, str(APP))

import pygame  # noqa: E402

from link.mailbox import CMD_ARRIVE, ROLE_AUTHORITY, ROLE_GUEST  # noqa: E402
from module import COOP_DISC  # noqa: E402
from session import Session  # noqa: E402

NZ0 = 0x0C
SAVE_ROOM = 200
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
    "explore": ("no0", "no1",
                "EXPLORE: apart in Marble Gallery / Outer Wall. Pick things up: does your partner get them? "
                "Check the map (SELECT) for your partner's marker.", None),
}

HELP = ("Pads: 1st controller = left game, 2nd = right game.  Keyboard: left game arrows + Z X C V "
        "(cross square circle triangle), A S = L1 R1, Enter = start, RShift = select;  right game "
        "I J K L + F G H T, Q E = L1 R1, Space = start, Tab = select.   F1 sound left/right   ESC quit")

SCALE = 2
W, H = 256, 240
BAR = 70

PAD_BUTTONS = {  # SDL game controller button -> PlayStation button name (harness/emu.py)
    pygame.CONTROLLER_BUTTON_A: "cross", pygame.CONTROLLER_BUTTON_B: "circle",
    pygame.CONTROLLER_BUTTON_X: "square", pygame.CONTROLLER_BUTTON_Y: "triangle",
    pygame.CONTROLLER_BUTTON_LEFTSHOULDER: "l1", pygame.CONTROLLER_BUTTON_RIGHTSHOULDER: "r1",
    pygame.CONTROLLER_BUTTON_BACK: "select", pygame.CONTROLLER_BUTTON_START: "start",
    pygame.CONTROLLER_BUTTON_DPAD_UP: "up", pygame.CONTROLLER_BUTTON_DPAD_DOWN: "down",
    pygame.CONTROLLER_BUTTON_DPAD_LEFT: "left", pygame.CONTROLLER_BUTTON_DPAD_RIGHT: "right",
}
KEYS = [  # per player: key -> button
    {pygame.K_UP: "up", pygame.K_DOWN: "down", pygame.K_LEFT: "left", pygame.K_RIGHT: "right",
     pygame.K_z: "cross", pygame.K_x: "square", pygame.K_c: "circle", pygame.K_v: "triangle",
     pygame.K_a: "l1", pygame.K_s: "r1", pygame.K_RETURN: "start", pygame.K_RSHIFT: "select"},
    {pygame.K_i: "up", pygame.K_k: "down", pygame.K_j: "left", pygame.K_l: "right",
     pygame.K_f: "cross", pygame.K_g: "square", pygame.K_h: "circle", pygame.K_t: "triangle",
     pygame.K_q: "l1", pygame.K_e: "r1", pygame.K_SPACE: "start", pygame.K_TAB: "select"},
]


class Audio:
    """One game's sound, through an SDL audio device fed from a small buffer."""

    def __init__(self):
        from pygame._sdl2 import audio as sdl_audio
        self.buf, self.lock = bytearray(), threading.Lock()
        self.dev = sdl_audio.AudioDevice(devicename=None, iscapture=False, frequency=44100,
                                         audioformat=sdl_audio.AUDIO_S16, numchannels=2, chunksize=1024,
                                         allowed_changes=0, callback=self._pull)
        self.dev.pause(0)

    def _pull(self, dev, mem):
        with self.lock:
            n = min(len(mem), len(self.buf))
            mem[:n] = self.buf[:n]
            del self.buf[:n]
        for i in range(n, len(mem)):
            mem[i] = 0

    def push(self, data):
        with self.lock:
            self.buf += data
            if len(self.buf) > 44100 * 4 // 5:  # over 0.2 s behind: drop the oldest
                del self.buf[:len(self.buf) - 44100 * 4 // 10]


FORMATS = {  # libretro pixel format -> (bits per pixel, RGB masks)
    0: (16, (0x7C00, 0x03E0, 0x001F, 0)),       # 0RGB1555
    1: (32, (0xFF0000, 0x00FF00, 0x0000FF, 0)),  # XRGB8888
    2: (16, (0xF800, 0x07E0, 0x001F, 0)),       # RGB565
}


def frame_surface(surf, fmt, pitch, height):
    """A surface the core's raw frame bytes can be written into as they are."""
    bits, masks = FORMATS[fmt]
    width = pitch * 8 // bits
    if surf is None or surf.get_size() != (width, height) or surf.get_bitsize() != bits:
        surf = pygame.Surface((width, height), 0, bits, masks)
    return surf


def pad_mask(player, controllers, keys):
    pressed = set()
    if player < len(controllers):
        c = controllers[player]
        pressed |= {name for btn, name in PAD_BUTTONS.items() if c.get_button(btn)}
        x, y = c.get_axis(pygame.CONTROLLER_AXIS_LEFTX), c.get_axis(pygame.CONTROLLER_AXIS_LEFTY)
        pressed |= {n for n, on in (("left", x < -16000), ("right", x > 16000), ("up", y < -16000), ("down", y > 16000)) if on}
        if c.get_axis(pygame.CONTROLLER_AXIS_TRIGGERLEFT) > 16000:
            pressed.add("l2")
        if c.get_axis(pygame.CONTROLLER_AXIS_TRIGGERRIGHT) > 16000:
            pressed.add("r2")
    pressed |= {name for key, name in KEYS[player].items() if keys[key]}
    return "+".join(sorted(pressed))


def setup(name, s):
    if name == "saveroom":
        s.a.mailbox("command", CMD_ARRIVE, NZ0, SAVE_ROOM, 48, 0xA4)  # by the coffin, not in it


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--preset", default="hall", choices=sorted(PRESETS))
    ap.add_argument("--fresh-cards", action="store_true", help="start both games with empty memory cards")
    ap.add_argument("--frames", type=int, default=0, help="quit after N frames (tests)")
    ap.add_argument("--shot", help="save a screenshot of the window at the end (tests)")
    ap.add_argument("--profile", action="store_true", help="print where each frame's time goes")
    args = ap.parse_args()
    start_a, start_b, goal, setup_name = PRESETS[args.preset]
    CARDS.mkdir(exist_ok=True)
    if args.fresh_cards:
        for f in CARDS.glob("*.mcd"):
            f.unlink()

    pygame.init()
    pygame.display.set_caption(f"SOTN Co-op playtest: {args.preset}")
    screen = pygame.display.set_mode((W * SCALE * 2 + 8, H * SCALE + BAR))
    font = pygame.font.SysFont("consolas", 14)
    from pygame._sdl2 import controller as sdl_controller
    sdl_controller.init()
    controllers = [sdl_controller.Controller(i) for i in range(sdl_controller.get_count())
                   if sdl_controller.is_controller(i)]
    try:
        audio = Audio()
    except Exception as exc:  # no sound device: play silent
        print("no audio:", exc)
        audio = None
    which_audio = 0

    with Session(COOP_DISC, starts=(start_a, start_b), session_file=CARDS / "session.coop", audio=True) as s:
        games = (s.a, s.b)
        for g, name in zip(games, "AB"):
            card = CARDS / f"{name}.mcd"
            if card.exists():
                g.load_card(card.read_bytes())
        if setup_name:
            setup(setup_name, s)
        clock, frame, last_cards = pygame.time.Clock(), 0, time.time()
        status = ""
        goal_lines = textwrap.wrap(goal, 145)[:2]
        lines = [font.render(t, True, (230, 230, 230)) for t in goal_lines + ["", HELP]]
        scaled = [None for _ in games]
        raw = [None for _ in games]
        prof = []
        running = True
        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                    running = False
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F1:
                    which_audio = 1 - which_audio
                elif ev.type == pygame.CONTROLLERDEVICEADDED:
                    controllers = [sdl_controller.Controller(i) for i in range(sdl_controller.get_count())
                                   if sdl_controller.is_controller(i)]
            keys = pygame.key.get_pressed()
            t0 = time.perf_counter()
            for i, g in enumerate(games):  # both games run their frame at the same time
                g.frame_start(pad_mask(i, controllers, keys))
            replies = [g.frame_end() for g in games]
            t1 = time.perf_counter()
            for i, (g, (picture, sound)) in enumerate(zip(games, replies)):
                if picture:
                    w, h, fmt, pitch, n = picture
                    raw[i] = frame_surface(raw[i], fmt, pitch, h)
                    raw[i].get_buffer().write(bytes(g.shm.buf[:n]), 0)
                    if scaled[i] is None or scaled[i].get_bitsize() != raw[i].get_bitsize():
                        scaled[i] = pygame.Surface((W * SCALE, H * SCALE), 0, raw[i])  # same pixel format
                    pygame.transform.scale(raw[i].subsurface((0, 0, w, h)), (W * SCALE, H * SCALE), scaled[i])
                    screen.blit(scaled[i], (i * (W * SCALE + 8), 0))
                if audio and i == which_audio:
                    audio.push(sound)
            frame += 1
            if s.joint and frame % 15 == 0:  # saves are rare: four frames a second is plenty
                s.joint.tick()
            if frame % 15 == 0:
                pa, pb = s.a.mailbox("self_presence"), s.b.mailbox("self_presence")
                role = {0: "-", ROLE_AUTHORITY: "authority", ROLE_GUEST: "guest"}
                shared = "SHARED ROOM" if {pa.role, pb.role} == {ROLE_AUTHORITY, ROLE_GUEST} else "apart"
                status = (f"left: stage {pa.stage:#04x} room {pa.room_left},{pa.room_top} {role[pa.role]}   "
                          f"right: stage {pb.stage:#04x} room {pb.room_left},{pb.room_top} {role[pb.role]}   "
                          f"{shared}   pads: {len(controllers)}   sound: {'left' if which_audio == 0 else 'right'}   "
                          f"{clock.get_fps():.0f} fps")
                lines = [font.render(t[:200], True, (230, 230, 230)) for t in goal_lines + [status, HELP]]
            screen.fill((16, 16, 24), (0, H * SCALE, screen.get_width(), BAR))
            for row, line in enumerate(lines):  # rendered 4 times a second: text is slow to draw
                screen.blit(line, (6, H * SCALE + 2 + row * 16))
            t2 = time.perf_counter()
            pygame.display.flip()
            if args.profile:
                prof.append((t1 - t0, t2 - t1, time.perf_counter() - t2))
                if len(prof) == 120:
                    print("ms per frame: games %.1f  draw %.1f  flip %.1f" % tuple(1000 * sum(x) / 120 for x in zip(*prof)), flush=True)
                    prof.clear()
            if time.time() - last_cards > 5 or not running:  # keep the memory cards on disk
                for g, name in zip(games, "AB"):
                    (CARDS / f"{name}.mcd").write_bytes(g.card())
                last_cards = time.time()
            if args.frames and frame >= args.frames:
                running = False
            clock.tick(60)
        if args.shot:
            pygame.image.save(screen, args.shot)
        for g, name in zip(games, "AB"):
            (CARDS / f"{name}.mcd").write_bytes(g.card())
    pygame.quit()


if __name__ == "__main__":
    main()
