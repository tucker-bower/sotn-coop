"""F9 reports: what leaves the player's device (no games run; ui_report_send is the whole flow).

    python launcher/test_report.py
"""

import http.server
import json
import sys
import tempfile
import threading
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "harness"))
import report  # noqa: E402

failed = 0


def check(ok, what):
    global failed
    failed += not ok
    print(("ok   " if ok else "FAIL ") + what)


home = str(Path.home())
dirty = f'{home} {json.dumps(home)[1:-1]} from 203.0.113.7:4000, 192.168.1.20'
clean = report.scrub(dirty)
check(home not in clean and "203.0.113.7" not in clean and "192.168.1.20" not in clean, "scrub: no home folder or IPs")

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
