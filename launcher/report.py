"""F9: a full environment snapshot, as one zip in reports/ (design/M6, D69).

Everything needed to see, and replay, what happened:
    now/          both games' savestates, memory cards, the joint save, both screens, the window,
                  and each screen with the game's own hitbox viewer on (A-hitboxes.png, hitboxes())
    before/       the in-memory states from about 5 and 10 s earlier (never written otherwise)
    inputs.json   both pads, the last 60 s
    link-A.json, link-B.json   each host's link traffic, the 60 s before F9
    journal.json  what changed, and when, for the whole session (rooms, scenes, deaths, the link)
    frames.json   frame times, the last 60 s
    about.json    versions, OS family, gameplay settings, how many controllers, presences, audio
                  stats, what last hurt each player (last_hit()), the player's note: only what
                  diagnosis needs (never paths or names)
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
import platform
import re
import struct
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

VERSION = "1.4.4"  # the launcher's
REPORT_EMAIL = "sotncoop@gmail.com"
SEND_URL = "https://api.resend.com/emails"
SEND_FROM = "SOTN Co-op <onboarding@resend.dev>"
KEY_FILE = Path(__file__).resolve().parent / "report_key.txt"
MAX_SEND = 28 * 2 ** 20  # a bigger zip can be emailed by hand, or asked for
PART_SIZE = 9 * 2 ** 20   # each attachment at most this: the inbox's reader takes 12 MB a file
IP = re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}\b")
SHARED_SETTINGS = ("music", "wide", "layout")  # nothing personal; the screen shape found #359
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


def snapshot(games, audio, run_frame=None):
    """What must be read the moment F9 is pressed, before the note box stops the clock. With
    run_frame, the games' hitboxes too (hitboxes())."""
    links = []
    for g in games:
        try:
            links.append(g.host("log_dump"))
        except Exception as e:  # noqa: BLE001 - a report should never fail to be written
            links.append({"error": str(e)})
    taken = {"links": links, "audio": audio.stats() if audio else None,
             "last_hit": [last_hit(g) for g in games]}
    taken["hitboxes"] = hitboxes(games, run_frame) if run_frame else [None for _ in games]
    return taken


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


# --- what the game itself knows about the moment (docs/research.md: the sotn.fun wiki)
ENTITIES, ENTITY_SIZE, N_ENTITIES = 0x800733D8, 0xBC, 256  # g_Entities
LAST_HIT = ENTITIES + 0xB8  # PLAYER.unkB8: the entity whose hitbox last touched the player (st/collision.h)
STAGE_ID = 0x800974A0       # g_StageId
DEBUG_ENABLED = 0x800BD1C0  # g_DebugEnabled: DRA draws hitboxes while it's set... (src/dra/42398.c)
HITBOX_MODE = 0x801362B0    # g_DebugHitboxViewMode: ...and this is 1-4 (the blend; 1 is half and half)
HITBOX_FRAMES = 3           # a screenshot shows the frame before: two frames drawn with them, and one


def last_hit(g):
    """What last hurt that game's player: its slot, id, update function (with the stage, enough to
    name it from the stage's map: scripts/read_report.py), place and numbers. The pointer stays
    after the entity is gone, so its slot may hold something else by now. None if it's no entity."""
    try:
        at = g.read(LAST_HIT)
        if not ENTITIES <= at < ENTITIES + N_ENTITIES * ENTITY_SIZE or (at - ENTITIES) % ENTITY_SIZE:
            return None
        e = g.read_bytes(at, ENTITY_SIZE)
    except Exception:  # noqa: BLE001 - a report should never fail to be written
        return None
    import struct
    x, y = struct.unpack_from("<hh", e, 2)[0], struct.unpack_from("<h", e, 6)[0]
    return {"slot": (at - ENTITIES) // ENTITY_SIZE, "id": struct.unpack_from("<H", e, 0x26)[0],
            "update": f"{struct.unpack_from('<I', e, 0x28)[0]:#010x}", "stage": g.read(STAGE_ID, "<H"),
            "x": x, "y": y, "hp": struct.unpack_from("<h", e, 0x3E)[0], "attack": struct.unpack_from("<h", e, 0x40)[0],
            "element": struct.unpack_from("<H", e, 0x42)[0], "params": struct.unpack_from("<H", e, 0x30)[0]}


def hitboxes(games, run_frame):
    """Each game's screen with DRA's own hitbox viewer on, for HITBOX_FRAMES frames (run_frame runs
    one frame of every game), then off again as it was. Drawing only: nothing the games decide
    reads these. [picture or None] per game."""
    try:
        before = [(g.read(DEBUG_ENABLED), g.read(HITBOX_MODE)) for g in games]
    except Exception:  # noqa: BLE001 - the fakes in test_report.py, a game gone
        return [None for _ in games]
    shots = []
    try:
        for g in games:
            g.write(DEBUG_ENABLED, 1)
            g.write(HITBOX_MODE, 1)
        for _ in range(HITBOX_FRAMES):
            run_frame()
        for g in games:
            try:
                shots.append(g.screenshot())
            except ImportError:  # the Android app has no PIL
                shots.append(None)
    finally:
        for g, (enabled, mode) in zip(games, before):
            g.write(DEBUG_ENABLED, enabled)
            g.write(HITBOX_MODE, mode)
    return shots


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
            "attachments": [{"filename": path.name + suffix, "content": base64.b64encode(chunk).decode()}
                            for suffix, chunk in parts(path.read_bytes())]}
    req = urllib.request.Request(SEND_URL, data=json.dumps(body).encode(), method="POST", headers={
        "Authorization": f"Bearer {KEY_FILE.read_text().strip()}", "Content-Type": "application/json",
        "User-Agent": f"sotn-coop/{VERSION}"})
    from link.tls import context
    tls = context()  # the system's roots and certifi's, as the relay (issue 351)
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


class _FastLZMA(zipfile.LZMACompressor):
    """zipfile's LZMA at preset 1: a savestate in a quarter of a second, not a second, and still
    two thirds of deflate's size (a 33 MB state: 1.84 MB, deflate 2.86 MB). Any unzip reads it."""

    def _init(self):
        import lzma
        f = {"id": lzma.FILTER_LZMA1, "preset": 1}
        props = lzma._encode_filter_properties(f)
        self._comp = lzma.LZMACompressor(lzma.FORMAT_RAW, filters=[f])
        return struct.pack("<BBH", 9, 4, len(props)) + props


def _open_zip(path):
    """A new report zip: LZMA where this Python has it (the Android app's doesn't), else deflate."""
    try:
        import lzma  # noqa: F401
    except ImportError:
        return zipfile.ZipFile(path, "x", zipfile.ZIP_DEFLATED)
    zipfile.LZMACompressor = _FastLZMA  # zipfile makes its compressors by this name
    return zipfile.ZipFile(path, "x", zipfile.ZIP_LZMA)


def parts(blob, size=PART_SIZE):
    """The report's attachments: [(suffix, bytes)]. One part is the zip itself; more are its
    bytes in order, named .part1-of-3 and so on (scripts/join_report.py puts them back)."""
    chunks = [blob[i:i + size] for i in range(0, len(blob), size)] or [b""]
    if len(chunks) == 1:
        return [("", chunks[0])]
    return [(f".part{k}-of-{len(chunks)}", c) for k, c in enumerate(chunks, 1)]


def write_launcher(window, note=""):
    """A report from the launcher's menus (F9 there, no game running): the window, the logs and
    what this install is. Returns its path."""
    from link.mailbox import LINK_VERSION
    from link.transport import WIRE_VERSION
    path = _new_path()
    private = private_words([], None)
    try:
        with _open_zip(path) as z:
            if window is not None:
                z.writestr("now/window.png", _png(window))
            patch = Path(__file__).resolve().parent.parent / "patcher/manifest.json"
            about = {"launcher": VERSION, "link": LINK_VERSION, "wire": WIRE_VERSION, "where": "launcher",
                     "patch": json.loads(patch.read_text()) if patch.exists() else None,
                     "settings": {k: v for k, v in load_settings().items() if k in SHARED_SETTINGS},
                     "os": f"{platform.system()} {platform.release()}", "python": platform.python_version(),
                     "note": note}
            z.writestr("about.json", scrub(json.dumps(about, indent=1, default=str), private))
            _add_logs(z, private)
    except OSError:
        path.unlink(missing_ok=True)
        raise
    return path


def _new_path():
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = reports_dir() / f"{stamp}.zip"
    k = 2
    while path.exists():
        path = reports_dir() / f"{stamp} ({k}).zip"
        k += 1
    return path


def _add_logs(z, private):
    for name in ("launcher.log", "session.log", "launcher-errors.log"):
        log = data_dir() / name
        if log.exists():
            z.writestr(name, scrub(log.read_text(errors="replace")[-LOG_TAIL:], private))


def write(games, playthrough, window, rolling, inputs, frame_times, controllers, note="", extra=None,
          taken=None, journal=None):
    """Writes the report; returns its path. games: the session's two games. taken: snapshot()."""
    from link.mailbox import LINK_VERSION
    from link.transport import WIRE_VERSION
    path = _new_path()
    taken = taken or snapshot(games, None)
    private = private_words(games, playthrough)
    try:
        with _open_zip(path) as z:
            for who, g, link in zip("AB", games, taken["links"]):
                z.writestr(f"now/{who}.state", scrub_bytes(g.save_state(), private))
                z.writestr(f"now/{who}.mcd", scrub_bytes(g.card(), private))
                try:
                    shot = g.screenshot()
                except ImportError:  # the Android app has no PIL: window.png still has the picture
                    shot = None
                if shot:
                    z.writestr(f"now/{who}.png", _png(shot))
                boxes = (taken.get("hitboxes") or [None, None])["AB".index(who)]
                if boxes:
                    z.writestr(f"now/{who}-hitboxes.png", _png(boxes))
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
                "last_hit": taken.get("last_hit"),
            }
            about.update(extra or {})
            z.writestr("about.json", scrub(json.dumps(about, indent=1, default=str), private))
            _add_logs(z, private)
    except OSError:  # a full disk: no half a report left behind (#277)
        path.unlink(missing_ok=True)
        raise
    return path
