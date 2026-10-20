"""The launcher's end-to-end check, without a screen (M6 criteria 4-6).

    python launcher/smoke.py <retail .cue> <patch .bps>

In a temporary data folder: makes the co-op disc, the debug starts, then plays a playthrough
from a debug start for a few seconds (both games, the real frame loop), and checks:
- savestates were made at the moments (a new area on arrival, quitting) and never overwritten;
- the space they take is what the home screen says;
- an F9 report has everything the design lists, and the savestates load back.
"""

import os
import sys
import tempfile
import zipfile
from pathlib import Path

os.environ["SDL_VIDEODRIVER"] = "dummy"
os.environ["SDL_AUDIODRIVER"] = "dummy"
os.environ["COOP_DATA"] = tempfile.mkdtemp(prefix="coop-smoke-")

import app  # noqa: E402 - sets up the paths

import archive  # noqa: E402
import debugstarts  # noqa: E402
import patcher  # noqa: E402
import paths  # noqa: E402


def check(cond, what, **info):
    print(("ok  " if cond else "BAD ") + what, info if info else "")
    if not cond:
        raise SystemExit(1)


def main():
    retail, patch = Path(sys.argv[1]), Path(sys.argv[2])
    launcher = app.Launcher()
    launcher.audio = None
    out = Path(os.environ["COOP_DATA"]) / "disc"
    cue = patcher.apply(retail, patch, out)
    launcher.settings.update(disc=str(cue), pads_set=True, bios=os.environ.get("COOP_BIOS"))
    paths.save_settings(launcher.settings)
    launcher.make_debug_starts()
    starts = debugstarts.load(launcher.starts_dir())
    check(len(starts) == len(debugstarts.STARTS), "debug starts made", n=len(starts))

    p = archive.Playthrough.new("Smoke test")
    file = str(launcher.starts_dir() / starts["Entrance hall"]["file"])
    from gameview import GameView
    with launcher.session((file, file), p) as s:
        view = GameView(s, launcher.screen, launcher.pads, None, p, frames=240,
                        save_cards=(p.card("A"), p.card("B")))
        view.run()
        report = view.report("smoke test note")
    pairs = p.savestate_pairs()
    labels = [label for label, _, _ in pairs]
    check(any("New area Castle Entrance" in x for x in labels), "a savestate on reaching a new area", labels=labels)
    check(any("Quit" in x for x in labels), "a savestate on quitting", labels=labels)
    check(all(a.exists() and b.exists() for _, a, b in pairs), "both games in each")
    size = p.savestates_size()
    check(size == archive.total_savestates_size() and size < 10 * 2 ** 20, "the space used is counted",
          size=paths.human(size), per_moment=paths.human(size / max(len(pairs), 1)))
    a, b = archive.load_pair(pairs[0][1], pairs[0][2])
    check(len(a) > 1 << 20 and len(b) > 1 << 20, "a savestate pair loads back")
    names = zipfile.ZipFile(report).namelist()
    want = ["now/A.state", "now/B.state", "now/A.mcd", "now/B.mcd", "now/A.png", "now/B.png", "now/window.png",
            "inputs.json", "frames.json", "link-A.json", "link-B.json", "about.json"]
    check(all(w in names for w in want) and any(n.startswith("before/") for n in names),
          "the F9 report has everything", missing=[w for w in want if w not in names])
    import json
    about = json.loads(zipfile.ZipFile(report).read("about.json"))
    check(about["note"] == "smoke test note" and about["link"] and about["os"], "with the note and versions")
    before = sorted(f.name for f in p.states.iterdir())
    p.savestate("Extra", _Fake(), "")
    after = sorted(f.name for f in p.states.iterdir())
    check(set(before) <= set(after) and len(after) == len(before) + 2, "a new savestate never replaces one")
    check_continue(launcher, starts)
    print("data folder:", os.environ["COOP_DATA"])


def check_continue(launcher, starts):
    """M6 criterion 3: save in a real coffin, quit; Continue resumes both games in the save room."""
    from session import SessionRun
    from session_saverooms import save_in_coffin
    from link.mailbox import BUSY, IN_PLAY
    p = archive.Playthrough.new("Continue test")
    file = str(launcher.starts_dir() / starts["Alchemy Lab: save room"]["file"])
    with launcher.session((file, file), p) as s:
        res = save_in_coffin(SessionRun(s, "continue"), s, s.a, s.b, p.joint_save)
        print("  save:", res, "seq", s.a.mailbox("save_seq"), s.b.mailbox("save_seq"), "card", s.b.mailbox("card_result"),
              "rooms", s.a.mailbox("self_presence").room, s.b.mailbox("self_presence").room, "joint", s.joint and s.joint.saves)
        for who, g in zip("AB", (s.a, s.b)):
            p.card(who).write_bytes(g.card())
    check(p.joint_save.exists(), "the joint save was written")
    with launcher.session((None, None), p) as s:  # what Continue does (Launcher.play)
        launcher.load_cards(s, p)
        check(launcher.boot_to_title(s, "Continuing"), "both games reached the title screen")
        s.joint.resume()
        for _ in range(1500):
            s.step(1)
            pa, pb = s.a.mailbox("self_presence"), s.b.mailbox("self_presence")
            if all(q.flags & IN_PLAY and not q.flags & BUSY for q in (pa, pb)):
                break
        check(pa.stage == pb.stage == 0x0C and pa.room_id == pb.room_id == 200,
              "Continue: both games are in play in the save room", a=str(pa.room), b=str(pb.room))


class _Fake:
    """Two stand-in games for the last check (the session is closed by then)."""

    def __iter__(self):
        class G:
            def save_state(self):
                return os.urandom(1000)
        return iter((G(), G()))


if __name__ == "__main__":
    main()
