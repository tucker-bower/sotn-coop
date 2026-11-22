"""The certificates the app's HTTPS trusts (the room-code relay, bug reports): issue 351.

Windows: Python reads only the roots already in the Windows store, and Windows adds a root
there only when its own networking first needs it. A PC that has never fetched Let's Encrypt's
root (ISRG Root X1) from Windows can't verify ntfy.sh, and the lobby says it can't reach the
room-code server. So the installer ships certifi (Mozilla's list, fresh each release), and this
trusts both: the system's store (antivirus and work roots) and certifi's list.

Android has no store Python can read: android/main.py makes a file of its CAs and names it in
SSL_CERT_FILE, which is trusted here too.
"""

import logging
import os
import socket
import ssl

log = logging.getLogger(__name__)


def context():
    """An SSL context for urllib that trusts the system's roots, SSL_CERT_FILE's and certifi's."""
    tls = ssl.create_default_context()
    for name, path in (("SSL_CERT_FILE", os.environ.get("SSL_CERT_FILE")), ("certifi", _certifi())):
        if not path:
            continue
        try:
            tls.load_verify_locations(cafile=path)
        except (OSError, ssl.SSLError) as e:
            log.warning("tls: can't load %s (%s): %r", name, path, e)
    return tls


def _certifi():
    try:
        import certifi
    except ImportError:
        return None
    return certifi.where()


def why(e):
    """What a failed HTTPS request means, in plain words for the lobby (None if it's unclear)."""
    import urllib.error
    if isinstance(e, urllib.error.HTTPError):
        if e.code == 429:
            return "it says this connection has made too many requests: wait a minute and try again"
        return f"it answered with an error ({e.code})"
    reason = getattr(e, "reason", e)  # URLError wraps the real one
    if isinstance(reason, ssl.SSLCertVerificationError):
        return ("this PC doesn't trust its certificate: antivirus that scans HTTPS can cause this "
                "(allow ntfy.sh in it)")
    if isinstance(reason, ssl.SSLError):
        return "the secure connection failed: antivirus or a filter may be interfering (allow ntfy.sh)"
    if isinstance(reason, socket.gaierror):
        return "its name didn't look up: this device is offline, or a DNS filter blocks ntfy.sh"
    if isinstance(reason, TimeoutError) or "timed out" in str(reason):
        return "it didn't answer in time: the connection is slow, or a firewall drops it"
    if isinstance(reason, (ConnectionRefusedError, ConnectionResetError)):
        return "the connection was refused or cut: a firewall or filter may block ntfy.sh"
    return None
