"""Updates from GitHub (design/launcher-overhaul.md, issue 82): at start-up, a look at the latest
release; if it's newer, the player is asked; yes downloads the installer (or, on Android, opens
the release page), checks it against the release's SHA256SUMS.txt, and runs it silently over
the same folder. The installer starts the launcher again. The player's data is never touched:
an update replaces only app\\ and python\\ (D196).

    Checker().start(); Checker().result  -> None (nothing to say) or a Release
    download(release, folder, progress) -> the checked installer's path
    install(path) -> starts it and returns (the launcher then quits)

Only a launcher that was installed looks (a dev checkout never does), at most once an hour, with a
3-second timeout: no answer, no prompt. It sends nothing but "sotn-coop/<version>".
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

API = "https://api.github.com/repos/tucker-bower/sotn-coop/releases/latest"
PAGE = "https://github.com/tucker-bower/sotn-coop/releases/latest"
INSTALLER, APK, SUMS = "SOTN-Coop-setup.exe", "SOTN-Coop.apk", "SHA256SUMS.txt"
TIMEOUT, EVERY = 3, 3600


def version(text):
    """ "v0.18.0" -> (0, 18, 0); anything else -> ()."""
    m = re.match(r"v?(\d+)\.(\d+)(?:\.(\d+))?", str(text or "").strip())
    return tuple(int(x or 0) for x in m.groups()) if m else ()


class Release:
    def __init__(self, data):
        self.tag = data.get("tag_name") or ""
        self.version = version(self.tag)
        self.name = self.tag.lstrip("v")
        self.page = data.get("html_url") or PAGE
        self.assets = {a.get("name"): a.get("browser_download_url") for a in data.get("assets") or [] if isinstance(a, dict)}
        self.notes = notes(data.get("body") or "")


def notes(body, lines=8):
    """The release's changelog for players, shortened: its "New" and "Fixed" items' first lines."""
    out = []
    for line in body.splitlines():
        line = line.strip()
        if line.startswith(("- ", "* ")):
            text = re.sub(r"\*\*|\[([^\]]*)\]\([^)]*\)|`", lambda m: m.group(1) or "", line[2:])
            out.append(text.split(". ")[0].rstrip("."))
        if len(out) >= lines:
            break
    return out


def latest(url=API, opener=None):
    """The latest published release, or None (no answer in TIMEOUT seconds, or not a release)."""
    from report import VERSION
    req = urllib.request.Request(url, headers={"User-Agent": f"sotn-coop/{VERSION}", "Accept": "application/vnd.github+json"})
    try:
        with (opener or urllib.request.urlopen)(req, timeout=TIMEOUT) as r:
            data = json.loads(r.read(1 << 20))
    except Exception:  # noqa: BLE001 - no network, rate limited, anything: no prompt
        return None
    return Release(data) if isinstance(data, dict) and data.get("tag_name") else None


def newer(release, mine):
    return bool(release and release.version and version(mine) and release.version > version(mine))


class Checker:
    """Looks in the background; result is the newer Release, or None."""

    def __init__(self, settings, mine, url=None, opener=None, installed=None):
        import paths
        self.settings, self.mine, self.opener = settings, mine, opener
        self.url = url or os.environ.get("COOP_UPDATE_URL") or API
        self.installed = paths.install_root() is not None if installed is None else installed
        self.result, self.done = None, False

    def wanted(self):
        """Installed (or a test's server), and not looked within the hour, unless it found one then."""
        if not (self.installed or os.environ.get("COOP_UPDATE_URL")):
            return False
        seen = self.settings.get("update_seen") or {}
        return not (time.time() - seen.get("at", 0) < EVERY and not seen.get("newer"))

    def start(self):
        if not self.wanted():
            self.done = True
            return self
        threading.Thread(target=self._run, daemon=True).start()
        return self

    def _run(self):
        r = latest(self.url, self.opener)
        self.settings["update_seen"] = {"at": time.time(), "newer": newer(r, self.mine)}
        self.result = r if newer(r, self.mine) else None
        self.done = True


def sums(text):
    """{file name: sha256} from a SHA256SUMS.txt."""
    out = {}
    for line in text.splitlines():
        m = re.match(r"([0-9a-fA-F]{64})\s+\*?(.+)$", line.strip())
        if m:
            out[m.group(2).strip()] = m.group(1).lower()
    return out


def download(release, folder, progress=None, opener=None, name=None):
    """The release's installer (or APK), checked against its SHA256SUMS.txt, in folder. Raises
    OSError in words for the player."""
    from report import VERSION
    name = name or (APK if _android() else INSTALLER)
    if name not in release.assets or SUMS not in release.assets:
        raise OSError(f"That release has no {name} to update from. Download it from the release page instead.")
    get = opener or urllib.request.urlopen

    def fetch(url, limit):
        req = urllib.request.Request(url, headers={"User-Agent": f"sotn-coop/{VERSION}"})
        data = bytearray()
        with get(req, timeout=30) as r:
            total = int(getattr(r, "headers", {}).get("Content-Length") or 0) if hasattr(r, "headers") else 0
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                data += chunk
                if len(data) > limit:
                    raise OSError("the download is far bigger than it should be")
                if progress and limit > 1 << 20:
                    progress(len(data), total or len(data))
        return bytes(data)
    try:
        want = sums(fetch(release.assets[SUMS], 1 << 16).decode("utf-8", "replace")).get(name)
        if not want:
            raise OSError(f"the release's {SUMS} doesn't list {name}")
        data = fetch(release.assets[name], 1 << 30)
    except OSError as e:
        raise OSError(f"Couldn't download the update ({e}). Check your internet and try again, or download it from the release page.") from e
    except Exception as e:  # noqa: BLE001
        raise OSError(f"Couldn't download the update ({e}).") from e
    if hashlib.sha256(data).hexdigest() != want:
        raise OSError("The download doesn't match the release's checksum, so it isn't used. Try again later.")
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / f"{Path(name).stem}-{release.name}{Path(name).suffix}"
    part = out.with_name(out.name + ".part")
    part.write_bytes(data)
    part.replace(out)
    return out


def install(path):
    """Starts the installer over this install, silently (it starts the launcher again when done).
    The caller quits at once: the installer replaces the program's files."""
    import paths
    root = paths.install_root()
    args = [str(path), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/SP-", "/CLOSEAPPLICATIONS"]
    if root:
        args.append(f"/DIR={root}")
    if os.environ.get("COOP_UPDATE_NOLAUNCH"):  # tests on a PC someone's using: the launcher doesn't start again
        args.append("/NOLAUNCH=1")
    if os.environ.get("COOP_UPDATE_DRY"):  # tests: written down, not run
        Path(os.environ["COOP_UPDATE_DRY"]).write_text(json.dumps(args))
        return
    flags = 0x00000008 | 0x00000200 if sys.platform == "win32" else 0  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(args, creationflags=flags, close_fds=True)


def tidy(folder):
    """The installers earlier updates downloaded: done with once the new version runs."""
    for f in Path(folder).glob("SOTN-Coop-setup-*"):
        try:
            f.unlink()
        except OSError:  # (an installer still running: next time)
            pass


def _android():
    try:
        from platform_android import ANDROID
        return ANDROID
    except Exception:  # noqa: BLE001
        return False
