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
    session.log   the game processes' log (connecting, the relay)
harness/replay.py opens these zips. Home folders and IP addresses are taken out of the text files.

send() emails a report (D144): Resend's API with a send-only key that build_release.sh and
android/build.sh put in report_key.txt. Its sandbox sender reaches only the key's own account,
REPORT_EMAIL, so all a key lifted from the app can do is fill that inbox. A build without a key
tells the player to email the zip themselves.
"""

import base64
import io
import json
import os
import platform
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from paths import data_dir, load_settings, reports_dir

VERSION = "0.13.0-dev"  # the launcher's
REPORT_EMAIL = "sotncoop@gmail.com"
SEND_URL = "https://api.resend.com/emails"
SEND_FROM = "SOTN Co-op <onboarding@resend.dev>"
KEY_FILE = Path(__file__).resolve().parent / "report_key.txt"
MAX_SEND = 28 * 2 ** 20  # a bigger zip can be emailed by hand, or asked for
IP = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")


def scrub(text):
    """A report's text, without the player's home folder or anyone's IP address."""
    home = str(Path.home())
    for form in (home, json.dumps(home)[1:-1]):
        text = text.replace(form, "~")
    return IP.sub("x.x.x.x", text)


def can_send():
    return KEY_FILE.is_file()


def send(path, note=""):
    """Emails a report. Returns None, or what went wrong, for the player."""
    path = Path(path)
    if path.stat().st_size > MAX_SEND:
        return "it's too big to send"
    body = {"from": SEND_FROM, "to": [REPORT_EMAIL], "subject": f"Bug report {path.stem} ({VERSION})",
            "text": note or "(no note)",
            "attachments": [{"filename": path.name, "content": base64.b64encode(path.read_bytes()).decode()}]}
    req = urllib.request.Request(SEND_URL, data=json.dumps(body).encode(), method="POST", headers={
        "Authorization": f"Bearer {KEY_FILE.read_text().strip()}", "Content-Type": "application/json",
        "User-Agent": f"sotn-coop/{VERSION}"})
    tls = ssl.create_default_context(cafile=os.environ.get("SSL_CERT_FILE") or None)  # as link/connect.py
    try:
        with urllib.request.urlopen(req, timeout=120, context=tls if SEND_URL.startswith("https") else None) as r:
            r.read()
    except urllib.error.HTTPError as e:
        return f"the mail service said {e.code}"
    except OSError:
        return "no connection"
    return None


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
    from link.transport import WIRE_VERSION
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
                z.writestr(f"link-{who}.json", scrub(json.dumps(g.host("log_dump"))))
            except Exception as e:  # noqa: BLE001 - a report should never fail to be written
                z.writestr(f"link-{who}.json", json.dumps({"error": str(e)}))
        if playthrough and playthrough.joint_save.exists():
            z.write(playthrough.joint_save, "now/session.coop")
        if window is not None:
            z.writestr("now/window.png", _png(window))
        for entry in rolling:
            frame, states = entry[0], entry[1:]
            for who, st in zip("AB", states):
                z.writestr(f"before/{frame}_{who}.state", st)
        z.writestr("inputs.json", json.dumps(list(inputs)))
        z.writestr("frames.json", json.dumps(list(frame_times)))
        patch = Path(__file__).resolve().parent.parent / "patcher/manifest.json"
        about = {
            "launcher": VERSION, "link": LINK_VERSION, "wire": WIRE_VERSION,
            "patch": json.loads(patch.read_text()) if patch.exists() else None,
            "settings": load_settings(), "os": platform.platform(), "python": sys.version,
            "controllers": controllers, "playthrough": playthrough.name if playthrough else None,
            "presences": [str(g.mailbox("self_presence")) for g in games],
            "rolling_frames": [entry[0] for entry in rolling], "note": note, "time": time.time(),
        }
        about.update(extra or {})
        z.writestr("about.json", scrub(json.dumps(about, indent=1, default=str)))
        for name in ("launcher.log", "session.log"):
            log = data_dir() / name
            if log.exists():
                z.writestr(name, scrub(log.read_text(errors="replace")))
    return path
