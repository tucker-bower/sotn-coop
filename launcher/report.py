"""F9: a full environment snapshot, as one zip in reports/ (design/M6, D69).

Everything needed to see, and replay, what happened:
    now/          both games' savestates, memory cards, the joint save, both screens, the window
    before/       the in-memory states from about 5 and 10 s earlier (never written otherwise)
    inputs.json   both pads, the last 60 s
    link-A.json, link-B.json   each host's link traffic, the last 60 s
    frames.json   frame times, the last 60 s
    about.json    versions (launcher, patch, link, core), disc and BIOS, OS, settings, controllers,
                  presences, the player's note
    launcher.log  the launcher's log
harness/replay.py opens these zips.
"""

import io
import json
import platform
import sys
import time
import zipfile
from pathlib import Path

from paths import data_dir, load_settings, reports_dir

VERSION = "0.6.0-dev"  # the launcher's


def _png(surface_or_image):
    buf = io.BytesIO()
    if hasattr(surface_or_image, "save") and not hasattr(surface_or_image, "get_size"):
        surface_or_image.save(buf, "PNG")
    else:
        import pygame
        pygame.image.save(surface_or_image, buf, "x.png")
    return buf.getvalue()


def write(games, playthrough, window, rolling, inputs, frame_times, controllers, note="", extra=None):
    """Writes the report; returns its path. games: the session's two games."""
    from link.mailbox import LINK_VERSION
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = reports_dir() / f"{stamp}.zip"
    k = 2
    while path.exists():
        path = reports_dir() / f"{stamp} ({k}).zip"
        k += 1
    with zipfile.ZipFile(path, "x", zipfile.ZIP_DEFLATED) as z:
        for who, g in zip("AB", games):
            z.writestr(f"now/{who}.state", g.save_state())
            z.writestr(f"now/{who}.mcd", g.card())
            shot = g.screenshot()
            if shot:
                z.writestr(f"now/{who}.png", _png(shot))
            try:
                z.writestr(f"link-{who}.json", json.dumps(g.host("log_dump")))
            except Exception as e:  # noqa: BLE001 - a report should never fail to be written
                z.writestr(f"link-{who}.json", json.dumps({"error": str(e)}))
        if playthrough and playthrough.joint_save.exists():
            z.write(playthrough.joint_save, "now/session.coop")
        if window is not None:
            z.writestr("now/window.png", _png(window))
        for frame, a, b in rolling:
            z.writestr(f"before/{frame}_A.state", a)
            z.writestr(f"before/{frame}_B.state", b)
        z.writestr("inputs.json", json.dumps(list(inputs)))
        z.writestr("frames.json", json.dumps(list(frame_times)))
        patch = Path(__file__).resolve().parent.parent / "patcher/manifest.json"
        about = {
            "launcher": VERSION, "link": LINK_VERSION,
            "patch": json.loads(patch.read_text()) if patch.exists() else None,
            "settings": load_settings(), "os": platform.platform(), "python": sys.version,
            "controllers": controllers, "playthrough": playthrough.name if playthrough else None,
            "presences": [str(g.mailbox("self_presence")) for g in games],
            "rolling_frames": [f for f, _, _ in rolling], "note": note, "time": time.time(),
        }
        about.update(extra or {})
        z.writestr("about.json", json.dumps(about, indent=1, default=str))
        log = data_dir() / "launcher.log"
        if log.exists():
            z.write(log, "launcher.log")
    return path
