"""F9: a full environment snapshot, as one zip in reports/ (design/M6, D69).

Everything needed to see, and replay, what happened:
    now/          both games' savestates, memory cards, the joint save, both screens, the window
    before/       the in-memory states from about 5 and 10 s earlier (never written otherwise)
    inputs.json   both pads, the last 60 s
    link-A.json, link-B.json   each host's link traffic, the 60 s before F9
    journal.json  what changed, and when, for the whole session (rooms, scenes, deaths, the link)
    frames.json   frame times, the last 60 s
    about.json    versions, OS family, gameplay settings, how many controllers, presences, audio
                  stats, the player's note: only what diagnosis needs (never paths or names)
    launcher.log  the launcher's log
    session.log   the game processes' log (connecting, the relay)
    launcher-errors.log   anything the launcher printed to stderr
harness/replay.py opens these zips. Folders, the disc's path, the typed name and IP addresses are
taken out of every file. In binary files the bytes are overwritten at the same length, so a
savestate still loads.

send() emails a report (D144): Resend's API with a send-only key that build_release.sh and
android/build.sh put in report_key.txt. Its sandbox sender reaches only the key's own account,
REPORT_EMAIL, so all a key lifted from the app can do is fill that inbox. A build without a key
tells the player to email the zip themselves.
"""

import base64
import collections
import io
import json
import logging
import os
import platform
import re
import ssl
import threading
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from link.jointsave import read_session, save_fields
from link.mailbox import BUSY, CS_FOLLOWER, CUTSCENE, DEAD, SAVE_DATA_SIZE
from paths import data_dir, load_settings, reports_dir

log = logging.getLogger("launcher")

VERSION = "1.1.0"  # the launcher's
REPORT_EMAIL = "sotncoop@gmail.com"
SEND_URL = "https://api.resend.com/emails"
SEND_FROM = "SOTN Co-op <onboarding@resend.dev>"
KEY_FILE = Path(__file__).resolve().parent / "report_key.txt"
MAX_SEND = 28 * 2 ** 20  # a bigger zip can be emailed by hand, or asked for
IP = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
SHARED_SETTINGS = ("music",)
LOG_TAIL = 500_000  # characters of each log
MIN_FOLDER = 4  # not a drive's root
MIN_NAME = 3  # a shorter typed name identifies no one, and its bytes turn up by chance in game RAM
CARD_BLOCK = 0x2000
FULL_WIDTH = {c: c + 0xFEE0 for c in range(0x21, 0x7F)}


def scrub(text, private=()):
    """A report's text, without the player's home folder, anyone's IP address, or `private`."""
    home = str(Path.home())
    for form in (home, json.dumps(home)[1:-1]):
        text = text.replace(form, "~")
    for word in private:
        for form in (word, json.dumps(word)[1:-1]):
            text = text.replace(form, "x" * len(form))
    return IP.sub("x.x.x.x", text)


def forms(word):
    """How a path or a name can sit in a binary file."""
    paths = {word, word.replace("\\", "/"), word.replace("/", "\\")}
    found = {f.encode("utf-8") for f in paths} | {f.encode("utf-16-le") for f in paths}
    try:  # the game keeps the typed name in Shift-JIS too
        found.add(word.translate(FULL_WIDTH).encode("shift_jis"))
    except UnicodeEncodeError:
        pass
    return found


def scrub_bytes(blob, private):
    """blob with each of `private` overwritten, at the same length: offsets stay right."""
    for form in sorted({f for word in private for f in forms(word)}, key=len, reverse=True):
        blob = blob.replace(form, b"x" * len(form))
    return blob


def card_names(card):
    """The names typed in a memory card's saves."""
    names = set()
    for at in range(CARD_BLOCK, len(card) - SAVE_DATA_SIZE + 1, CARD_BLOCK):
        names.add(save_fields(card[at:at + SAVE_DATA_SIZE])[0])
    return names


def private_words(games, playthrough):
    """Everything a report must not carry: the player's folders and typed names."""
    settings = load_settings()
    # The folders only: a savestate won't load without its disc's file name (not private anyway).
    folders = {str(Path(settings[k]).parent) for k in ("disc", "bios") if settings.get(k)}
    paths = {str(Path.home()), str(data_dir())} | {f for f in folders if len(f) >= MIN_FOLDER}
    names = set()
    for g in games:
        names |= card_names(g.card())
    if playthrough:
        names.add(playthrough.info.get("name") or "")
        if playthrough.joint_save.exists():
            names |= {save_fields(b)[0] for b in read_session(playthrough.joint_save)}
    return sorted(paths | {n for n in names if len(n) >= MIN_NAME})


def snapshot(games, audio):
    """What must be read the moment F9 is pressed, before the note box stops the clock."""
    links = []
    for g in games:
        try:
            links.append(g.host("log_dump"))
        except Exception as e:  # noqa: BLE001 - a report should never fail to be written
            links.append({"error": str(e)})
    return {"links": links, "audio": audio.stats() if audio else None}


class Journal:
    """A line per change, for the whole session: savestates reach back seconds, a softlock's
    cause can be many minutes older. Called from the status update, so it costs nothing extra."""

    def __init__(self):
        self.events, self.last, self.t0 = collections.deque(maxlen=5000), {}, time.monotonic()

    def _add(self, frame, what, *detail):
        self.events.append((round(time.monotonic() - self.t0, 1), frame, what, *detail))

    def note(self, frame, presences, link=None):
        for who, p in zip("AB", presences):
            state = (p.stage, p.room_left, p.room_top, p.flags)
            if self.last.get(who) != state:
                self.last[who] = state
                self._add(frame, who, *state, p.x, p.y, flag_names(p.flags))
        if link != self.last.get("link"):
            self.last["link"] = link
            self._add(frame, "link", link)


def flag_names(flags):
    return " ".join(n for n, bit in (("busy", BUSY), ("dead", DEAD), ("cutscene", CUTSCENE),
                                     ("follower", CS_FOLLOWER)) if flags & bit)


def can_send():
    return KEY_FILE.is_file()


# --- the outbox: a report the player chose to send waits beside its zip (<zip>.send, its note)
# until it's sent. One thread sends them one at a time, and tries again later and at the next
# start: sent from the game view's own thread, four of a playtester's seven reports were lost
# (2026-11-14), with nothing logged.
RETRY_SECONDS = 120
_outbox_lock = threading.Lock()
_outbox_thread = None
_outbox_done = []  # (path, error or None), for whoever wants to say so (the game view)


def queue_send(path, note=""):
    """Sends a report in the background, until it's gone (see the outbox above)."""
    path = Path(path)
    try:
        path.with_name(path.name + ".send").write_text(json.dumps({"note": note}))
    except OSError:
        log.exception("queueing a report")
    start_outbox()


def pending():
    """The reports waiting to be sent, oldest first."""
    return sorted(p.with_name(p.name[:-len(".send")]) for p in reports_dir().glob("*.zip.send"))


def start_outbox():
    """The outbox's thread, unless it's running already (at startup: what an earlier run left)."""
    global _outbox_thread
    if not can_send():
        return
    with _outbox_lock:
        if _outbox_thread and _outbox_thread.is_alive():
            return
        _outbox_thread = threading.Thread(target=_outbox_run, daemon=True, name="report outbox")
        _outbox_thread.start()


def _outbox_run():
    failures = {}
    while True:
        waiting = [p for p in pending() if time.time() >= failures.get(p, (0, 0))[1]]
        if not waiting:
            if not pending():
                return
            time.sleep(min(5, RETRY_SECONDS))
            continue
        path = waiting[0]
        marker = path.with_name(path.name + ".send")
        if not path.exists():  # the player deleted it
            marker.unlink(missing_ok=True)
            continue
        try:
            note = json.loads(marker.read_text()).get("note", "")
        except (OSError, ValueError):
            note = ""
        error = send(path, note)
        if error is None:
            log.info("bug report sent: %s", path.name)
            marker.unlink(missing_ok=True)
            failures.pop(path, None)
        else:
            tries = failures.get(path, (0, 0))[0] + 1
            log.warning("bug report %s not sent (try %d): %s", path.name, tries, error)
            if tries >= 5 or error == "it's too big to send":  # left for the next start
                return _outbox_done.append((path, error))
            failures[path] = (tries, time.time() + RETRY_SECONDS * tries)
            if tries > 1:
                continue
        _outbox_done.append((path, error))


def outbox_news():
    """[(path, error or None)] since the last call: what the outbox sent, or first failed to."""
    out = _outbox_done[:]
    del _outbox_done[:len(out)]
    return out


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
        try:
            said = e.read()[:300].decode(errors="replace")
        except OSError:
            said = ""
        log.warning("the mail service said %s: %s", e.code, said)
        return f"the mail service said {e.code}"
    except OSError as e:
        log.warning("sending a report: %s", e)
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


def write(games, playthrough, window, rolling, inputs, frame_times, controllers, note="", extra=None,
          taken=None, journal=None):
    """Writes the report; returns its path. games: the session's two games. taken: snapshot()."""
    from link.mailbox import LINK_VERSION
    from link.transport import WIRE_VERSION
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = reports_dir() / f"{stamp}.zip"
    k = 2
    while path.exists():
        path = reports_dir() / f"{stamp} ({k}).zip"
        k += 1
    taken = taken or snapshot(games, None)
    private = private_words(games, playthrough)
    try:
        with zipfile.ZipFile(path, "x", zipfile.ZIP_DEFLATED) as z:
            for who, g, link in zip("AB", games, taken["links"]):
                z.writestr(f"now/{who}.state", scrub_bytes(g.save_state(), private))
                z.writestr(f"now/{who}.mcd", scrub_bytes(g.card(), private))
                try:
                    shot = g.screenshot()
                except ImportError:  # the Android app has no PIL: window.png still has the picture
                    shot = None
                if shot:
                    z.writestr(f"now/{who}.png", _png(shot))
                z.writestr(f"link-{who}.json", scrub(json.dumps(link), private))
            if playthrough and playthrough.joint_save.exists():
                z.writestr("now/session.coop", scrub_bytes(playthrough.joint_save.read_bytes(), private))
            if window is not None:
                z.writestr("now/window.png", _png(window))
            for entry in rolling:
                frame, states = entry[0], entry[1:]
                for who, st in zip("AB", states):
                    z.writestr(f"before/{frame}_{who}.state", scrub_bytes(st, private))
            z.writestr("inputs.json", json.dumps(list(inputs)))
            z.writestr("frames.json", json.dumps(list(frame_times)))
            z.writestr("journal.json", json.dumps(list(journal.events) if journal else []))
            patch = Path(__file__).resolve().parent.parent / "patcher/manifest.json"
            about = {
                "launcher": VERSION, "link": LINK_VERSION, "wire": WIRE_VERSION,
                "patch": json.loads(patch.read_text()) if patch.exists() else None,
                "settings": {k: v for k, v in load_settings().items() if k in SHARED_SETTINGS},
                "os": f"{platform.system()} {platform.release()}", "python": platform.python_version(),
                "controllers": len(controllers), "castle": bool(playthrough),
                "presences": [str(g.mailbox("self_presence")) for g in games],
                "rolling_frames": [entry[0] for entry in rolling], "note": note, "audio": taken["audio"],
            }
            about.update(extra or {})
            z.writestr("about.json", scrub(json.dumps(about, indent=1, default=str), private))
            for name in ("launcher.log", "session.log", "launcher-errors.log"):
                log = data_dir() / name
                if log.exists():
                    z.writestr(name, scrub(log.read_text(errors="replace")[-LOG_TAIL:], private))
    except OSError:  # a full disk: no half a report left behind (#277)
        path.unlink(missing_ok=True)
        raise
    return path
