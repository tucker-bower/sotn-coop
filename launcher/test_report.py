"""F9 reports: what leaves the player's device (no games run; ui_report_send is the whole flow).

    python launcher/test_report.py
"""

import http.server
import json
import sys
import tempfile
import threading
import types
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "harness"))
import report  # noqa: E402

failed = 0
DISC = "D:/Games/My Tucker Rips/sotn disc.cue"
NAME = "Zhikajira"
PAD = "Acme Pro Controller"
report_name_at = 0x200


def check(ok, what):
    global failed
    failed += not ok
    print(("ok   " if ok else "FAIL ") + what)


home = str(Path.home())
dirty = f'{home} {json.dumps(home)[1:-1]} from 203.0.113.7:4000, 192.168.1.20'
clean = report.scrub(dirty)
check(home not in clean and "203.0.113.7" not in clean and "192.168.1.20" not in clean, "scrub: no home folder or IPs")



class Game:
    """Holds a typed name and paths the way a real game's memory does."""
    def __init__(self, words):
        self.blob = b"\0".join(f for w in words for f in report.forms(w))

    def save_state(self):
        return self.blob

    def card(self):
        save = bytearray(report.SAVE_DATA_SIZE)
        save[report_name_at:report_name_at + len(NAME)] = NAME.encode()
        return bytes(report.CARD_BLOCK) + bytes(save) + bytes(0x20000 - report.CARD_BLOCK - len(save))

    def screenshot(self):
        return None

    def host(self, name):
        return [[1.0, "out", DISC]]

    def mailbox(self, name):
        return f"presence {NAME}"


class Castle:
    info = {"name": NAME}
    joint_save = Path("does-not-exist")


with tempfile.TemporaryDirectory() as d:
    report.reports_dir = lambda: Path(d)
    report.data_dir = lambda: Path(d)
    report.load_settings = lambda: {"disc": DISC, "bios": None, "music": "auto", "pads": [PAD, None]}
    Path(d, "launcher-errors.log").write_text(f"Traceback in {DISC}\n")
    games = [Game([DISC, home, NAME]), Game([DISC, home, NAME])]
    journal = report.Journal()
    path = report.write(games, Castle(), None, [(300, games[0].save_state(), games[1].save_state())], [], [], [PAD],
                        "my note", {"solo": None}, journal=journal)
    with zipfile.ZipFile(path) as z:
        files = {n: z.read(n) for n in z.namelist()}
    check("launcher-errors.log" in files and "journal.json" in files, "the errors log and the journal are in it")
    size = len(games[0].save_state())
    check(len(files["now/A.state"]) == size and len(files[f"before/300_A.state"]) == size, "states keep their size")
    leaks = [(n, w) for n, data in files.items() for w in (str(Path(DISC).parent), home, NAME, PAD) for f in report.forms(w) if f in data]
    check(not leaks, f"no planted identifier anywhere in the report, binary files included: {leaks[:4]}")
    about = json.loads(files["about.json"])
    check(about["controllers"] == 1 and set(about["settings"]) == {"music"}, "about.json keeps only what's needed")
    check("time" not in about and "pads" not in about["settings"], "no timestamp or pads in about.json")



class NoPilGame(Game):
    def screenshot(self):  # as on Android (0.16.0: F9 there closed the app)
        raise ModuleNotFoundError("No module named 'PIL'")


with tempfile.TemporaryDirectory() as d:
    report.reports_dir = lambda: Path(d)
    games = [NoPilGame([DISC]), NoPilGame([DISC])]
    path = report.write(games, Castle(), None, [], [], [], [PAD], "", {"solo": None})
    with zipfile.ZipFile(path) as z:
        check("now/A.state" in z.namelist() and "now/A.png" not in z.namelist(),
              "without PIL (Android), the report is written, without the games' own pictures")

journal = report.Journal()
P = types.SimpleNamespace
stuck = P(stage=11, room_left=2, room_top=3, flags=64 | 128, x=1, y=2)
for frame in (1, 2, 3):
    journal.note(frame, [stuck], "here")
journal.note(4, [P(stage=11, room_left=2, room_top=4, flags=16, x=1, y=2)], "lost")
events = list(journal.events)
check(len(events) == 4 and events[0][-1] == "cutscene follower" and events[-2][-1] == "dead" and events[-1][-1] == "lost",
      "the journal keeps changes, not frames")

replies = []
got = []


class Mail(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        got.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        self.send_response(replies.pop(0))
        self.end_headers()

    def log_message(self, *a):
        pass


mail = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Mail)
threading.Thread(target=mail.serve_forever, daemon=True).start()
report.SEND_URL = f"http://127.0.0.1:{mail.server_port}/emails"
with tempfile.TemporaryDirectory() as d:
    zip_file, report.KEY_FILE = Path(d) / "r.zip", Path(d) / "report_key.txt"
    zip_file.write_bytes(b"zip")
    check(not report.can_send(), "no key: this build can't send")
    report.KEY_FILE.write_text("k\n")
    check(report.can_send(), "a key: it can")
    replies.append(200)
    check(report.send(zip_file, "note") is None, "a sent report: no error")
    check(got[-1]["to"] == ["sotncoop@gmail.com"] and got[-1]["attachments"][0]["filename"] == "r.zip",
          "it goes to the reports address, with the zip")
    replies.append(429)
    check("429" in (report.send(zip_file) or ""), "a refusal is reported, not raised")
    mail.shutdown()
    mail.server_close()
    check(report.send(zip_file) == "no connection", "no connection is reported, not raised")
    report.MAX_SEND = 1
    check("too big" in (report.send(zip_file) or ""), "an oversized report isn't sent")
sys.exit(1 if failed else 0)
