"""Updates (launcher/update.py, design/launcher-overhaul.md criteria 1 and 2) against a fake GitHub on
localhost: a newer release is found, an older or equal one isn't, no answer means no prompt and
no wait; the installer downloads and is checked against SHA256SUMS.txt, a wrong one is refused;
the installer is started silently over the same folder. Nothing is installed.

    python launcher/test_update.py
"""

import hashlib
import json
import os
import socket
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

import update  # noqa: E402

failures = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


class GitHub(BaseHTTPRequestHandler):
    files = {}

    def do_GET(self):
        body = self.files.get(self.path)
        if body is None:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def main():
    check(update.version("v0.18.0") == (0, 18, 0) and update.version("0.9") == (0, 9, 0) and update.version("beta") == (),
          "versions read from tags")
    check(update.notes("**New**\n- **Play a randomized castle together.** Make a seed on [sotn.io](https://sotn.io). Then more.\n"
                       "- Fixed `this`.\nPlain text") == ["Play a randomized castle together", "Fixed this"],
          "the changelog: each item's first sentence, without its markup")

    server = HTTPServer(("127.0.0.1", 0), GitHub)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_port}"
    installer = b"MZ the new installer" * 1000

    def publish(tag, sums_for=installer):
        GitHub.files.clear()
        GitHub.files["/latest"] = json.dumps({
            "tag_name": tag, "html_url": base + "/page", "body": "### New\n- **A new thing.** More.",
            "assets": [{"name": update.INSTALLER, "browser_download_url": base + "/setup.exe"},
                       {"name": update.SUMS, "browser_download_url": base + "/sums"}]}).encode()
        GitHub.files["/setup.exe"] = installer
        GitHub.files["/sums"] = f"{hashlib.sha256(sums_for).hexdigest()}  {update.INSTALLER}\n0000  other.apk\n".encode()

    publish("v0.18.0")
    r = update.latest(base + "/latest")
    check(r and r.name == "0.18.0" and update.newer(r, "0.17.0") and not update.newer(r, "0.18.0") and not update.newer(r, "0.19.1"),
          "the latest release: newer than 0.17.0, not than 0.18.0 or 0.19.1")
    check(r.notes == ["A new thing"], "with its changelog")

    dead = socket.socket()
    dead.bind(("127.0.0.1", 0))
    port = dead.getsockname()[1]
    dead.close()
    t0 = time.time()
    check(update.latest(f"http://127.0.0.1:{port}/latest") is None and time.time() - t0 < update.TIMEOUT + 1,
          "nobody answering: no release, within the timeout")
    check(update.latest(base + "/missing") is None, "not a release: none")

    st = {}
    c = update.Checker(st, "0.17.0", url=base + "/latest", installed=False).start()
    check(c.done and c.result is None and "update_seen" not in st, "a dev checkout never looks")
    c = update.Checker(st, "0.17.0", url=base + "/latest", installed=True).start()
    t0 = time.time()
    while not c.done and time.time() - t0 < 5:
        time.sleep(0.05)
    check(c.result and c.result.name == "0.18.0" and st["update_seen"]["newer"], "installed, it looks in the background and finds 0.18.0")
    st["update_seen"] = {"at": time.time(), "newer": False}
    check(not update.Checker(st, "0.17.0", url=base + "/latest", installed=True).wanted(), "looked within the hour, nothing found: not again")

    with tempfile.TemporaryDirectory() as d:
        seen = []
        path = update.download(r, d, lambda got, of: seen.append(got))
        check(path.read_bytes() == installer and path.name == "SOTN-Coop-setup-0.18.0.exe", "the installer downloads, checked against SHA256SUMS.txt")
        publish("v0.18.0", sums_for=b"something else")
        r2 = update.latest(base + "/latest")
        try:
            update.download(r2, Path(d) / "bad")
            check(False, "a download that doesn't match its checksum is refused")
        except OSError as e:
            check("checksum" in str(e) and not (Path(d) / "bad").exists(), f"a download that doesn't match its checksum is refused, and not kept: {e}")
        r2.assets.pop(update.INSTALLER)
        try:
            update.download(r2, d)
            check(False, "a release without an installer: says so")
        except OSError as e:
            check("release page" in str(e), "a release without an installer: says so")

        os.environ["COOP_INSTALL_ROOT"] = str(Path(d) / "Games" / "sotn-coop")
        os.environ["COOP_UPDATE_DRY"] = str(Path(d) / "args.json")
        update.install(path)
        args = json.loads(Path(os.environ["COOP_UPDATE_DRY"]).read_text())
        check(args[0] == str(path) and "/VERYSILENT" in args and f"/DIR={Path(d) / 'Games' / 'sotn-coop'}" in args,
              "the installer is started silently, over the same folder")
    server.shutdown()
    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
