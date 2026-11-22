"""The app's HTTPS trust and the relay's failures (issue 351): a PC whose system store lacks the
relay's root still verifies ntfy.sh, a failure names its cause, and reading backs off.

    python link/test_tls.py

The first check runs in a child Python whose system store is empty (SSL_CERT_FILE and
SSL_CERT_DIR point at nothing), as on a Windows PC that never fetched Let's Encrypt's root."""

import os
import socket
import ssl
import subprocess
import sys
import tempfile
import urllib.error
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from link import connect, tls  # noqa: E402

fails = []


def check(ok, what):
    print(f"{'ok  ' if ok else 'FAIL'} {what}")
    if not ok:
        fails.append(what)


CHILD = """
import ssl, sys
sys.path.insert(0, sys.argv[1])
from link import tls
def isrg(ctx):
    return any(dict(x[0] for x in c["subject"]).get("commonName") == "ISRG Root X1" for c in ctx.get_ca_certs())
print(isrg(ssl.create_default_context()), isrg(tls.context()))
"""


def main():
    root = str(Path(__file__).resolve().parent.parent)
    with tempfile.TemporaryDirectory() as d:
        empty = Path(d, "none.pem")
        empty.write_text("")
        env = dict(os.environ, SSL_CERT_FILE=str(empty), SSL_CERT_DIR=d)
        out = subprocess.run([sys.executable, "-c", CHILD, root], env=env, capture_output=True, text=True).stdout.split()
    check(out == ["False", "True"],
          f"a system store without Let's Encrypt's root: Python's own context lacks it, ours has it (certifi) {out}")

    cert = urllib.error.URLError(ssl.SSLCertVerificationError(1, "certificate verify failed: unable to get local issuer certificate"))
    cases = [
        (cert, "trust its certificate"),
        (urllib.error.URLError(socket.gaierror(11001, "getaddrinfo failed")), "DNS"),
        (urllib.error.URLError(TimeoutError("timed out")), "in time"),
        (urllib.error.URLError(ConnectionRefusedError(10061, "refused")), "refused"),
        (urllib.error.HTTPError("https://ntfy.sh/x", 429, "Too Many Requests", {}, None), "too many requests"),
    ]
    for e, words in cases:
        said = tls.why(e) or ""
        check(words in said, f"{type(getattr(e, 'reason', e)).__name__}: the player is told {said!r:.70}")

    # reading after errors: waits 2, 4, 8, 16, 30, 30 s, not 2 s each time
    relay, waits = connect.NtfyRelay(), []

    def fail(*a, **k):
        raise cert

    def sleep(s):
        waits.append(s)
        if len(waits) >= 6:
            relay.close()
    real = connect.urllib.request.urlopen, connect.time.sleep
    connect.urllib.request.urlopen, connect.time.sleep = fail, sleep
    try:
        relay._stream("t")
    finally:
        connect.urllib.request.urlopen, connect.time.sleep = real
    check(waits == [2, 4, 8, 16, 30, 30], f"reading the relay backs off after errors {waits}")
    check("trust its certificate" in (relay.why or ""), "the relay keeps the cause for the lobby's failure message")

    print(f"\n{'all passed' if not fails else f'{len(fails)} FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
