"""Discord shows "Playing SoTN Co-op" (Tucker, 2026-11-19): Rich Presence through the Discord app on
this PC, over its local IPC pipe. No account, server or library of ours: the app talks to Discord
the way any game does, and nothing happens when Discord isn't running.

The activity's name is the Discord application's (CLIENT_ID, registered on Discord's developer
portal as "SoTN Co-op"). What's shown: what the player is doing ("In the menus", "Online co-op",
"Couch co-op", "Boss rush"), the castle's name, how long, and online how many are in the room. Never
a room code or an address (streamer mode or not).

    status = DiscordStatus(); status.set("Online co-op", "Castle: Tucker", party=(2, 4)); status.close()

The protocol: frames of (opcode u32, length u32, JSON), little-endian; a handshake (op 0, the client
id), then SET_ACTIVITY commands (op 1). Windows: the named pipe \\\\.\\pipe\\discord-ipc-N; elsewhere
the socket $XDG_RUNTIME_DIR (or TMPDIR, /tmp)/discord-ipc-N, N from 0 to 9.
"""

import json
import logging
import os
import socket
import struct
import sys
import threading
import time
import uuid

CLIENT_ID = os.environ.get("COOP_DISCORD_CLIENT_ID", "")  # the Discord application "SoTN Co-op" (to register)
RETRY_S = 15          # Discord not running: try again this often
MIN_GAP_S = 4         # Discord allows 5 updates in 20 s
log = logging.getLogger("discord")


def _paths():
    if sys.platform == "win32":
        return [rf"\\.\pipe\discord-ipc-{n}" for n in range(10)]
    base = os.environ.get("XDG_RUNTIME_DIR") or os.environ.get("TMPDIR") or "/tmp"
    out = []
    for sub in ("", "app/com.discordapp.Discord", "snap.discord"):  # (Flatpak and Snap Discord too)
        out += [os.path.join(base, sub, f"discord-ipc-{n}") for n in range(10)]
    return out


class _Pipe:
    def __init__(self):
        self.f = self.s = None
        for path in _paths():
            try:
                if sys.platform == "win32":
                    self.f = open(path, "r+b", buffering=0)
                else:
                    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                    s.settimeout(2)
                    s.connect(path)
                    self.s = s
                return
            except OSError:
                continue
        raise OSError("Discord isn't running")

    def send(self, op, payload):
        data = json.dumps(payload).encode()
        frame = struct.pack("<II", op, len(data)) + data
        if self.f:
            self.f.write(frame)
        else:
            self.s.sendall(frame)

    def recv(self):
        head = self._read(8)
        op, n = struct.unpack("<II", head)
        return op, json.loads(self._read(n) or b"{}")

    def _read(self, n):
        out = b""
        while len(out) < n:
            chunk = self.f.read(n - len(out)) if self.f else self.s.recv(n - len(out))
            if not chunk:
                raise OSError("Discord closed the pipe")
            out += chunk
        return out

    def close(self):
        for c in (self.f, self.s):
            try:
                if c:
                    c.close()
            except OSError:
                pass


class DiscordStatus:
    """The player's Discord status, kept up to date from a thread of its own (never the game's)."""

    def __init__(self, client_id=None, enabled=True):
        self.client_id = client_id if client_id is not None else CLIENT_ID
        self.enabled = enabled and bool(self.client_id) and not os.environ.get("COOP_NO_DISCORD")
        self._want = None   # the activity to show, or None (clear)
        self._shown = object()
        self._wake = threading.Event()
        self._stop = False
        self._thread = None
        if self.enabled:
            self._thread = threading.Thread(target=self._run, name="discord", daemon=True)
            self._thread.start()

    def set(self, details, state=None, party=None, started=None):
        """details: what the player is doing; state: the castle, a second line; party: (in the room,
        at most); started: when (a time.time()), for Discord's "elapsed"."""
        activity = {"details": details[:128], "timestamps": {"start": int(started or time.time())},
                    "assets": {"large_image": "logo", "large_text": "SoTN Co-op"}}
        if state:
            activity["state"] = state[:128]
        if party and party[1] > 1:
            activity["party"] = {"id": "room", "size": [max(1, party[0]), party[1]]}
        self._want = activity
        self._wake.set()

    def clear(self):
        self._want = None
        self._wake.set()

    def close(self):
        self._stop = True
        self._wake.set()

    def _run(self):
        pipe, last = None, 0.0
        while not self._stop:
            if pipe is None:
                try:
                    pipe = _Pipe()
                    pipe.send(0, {"v": 1, "client_id": self.client_id})
                    pipe.recv()  # READY
                    self._shown = object()
                except OSError:
                    pipe = None
                    self._wake.wait(RETRY_S)
                    self._wake.clear()
                    continue
            want = self._want
            if want is not self._shown:
                gap = MIN_GAP_S - (time.time() - last)
                if gap > 0:
                    time.sleep(gap)
                    continue
                try:
                    pipe.send(1, {"cmd": "SET_ACTIVITY", "args": {"pid": os.getpid(), "activity": want},
                                  "nonce": str(uuid.uuid4())})
                    pipe.recv()
                    self._shown, last = want, time.time()
                except OSError as e:
                    log.info("Discord status: %s", e)
                    pipe.close()
                    pipe = None
                    continue
            self._wake.wait(RETRY_S)
            self._wake.clear()
        if pipe is not None:
            try:
                pipe.send(1, {"cmd": "SET_ACTIVITY", "args": {"pid": os.getpid()}, "nonce": str(uuid.uuid4())})
            except OSError:
                pass
            pipe.close()
