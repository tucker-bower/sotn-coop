"""The Discord status (launcher/discord_status.py) against a fake Discord: the IPC socket it looks
for, speaking Discord's frames. Not on Windows (its named pipe): the code past the connect is the same.

    python launcher/test_discord_status.py
"""
import json
import os
import socket
import struct
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
fails = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        fails.append(what)


def frame(conn):
    head = b""
    while len(head) < 8:
        head += conn.recv(8 - len(head))
    op, n = struct.unpack("<II", head)
    body = b""
    while len(body) < n:
        body += conn.recv(n - len(body))
    return op, json.loads(body)


def send(conn, op, payload):
    data = json.dumps(payload).encode()
    conn.sendall(struct.pack("<II", op, len(data)) + data)


def main():
    tmp = tempfile.mkdtemp(prefix="coop-discord-")
    os.environ["XDG_RUNTIME_DIR"] = tmp
    import discord_status
    discord_status.MIN_GAP_S, discord_status.RETRY_S = 0.05, 0.2

    # No Discord running: nothing happens, nothing raises
    st = discord_status.DiscordStatus(client_id="123")
    st.set("In the menus")
    time.sleep(0.3)
    st.close()
    check(True, "no Discord: the app carries on")

    seen = []
    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(os.path.join(tmp, "discord-ipc-0"))
    server.listen(1)

    def discord():
        conn, _ = server.accept()
        seen.append(frame(conn))
        send(conn, 1, {"cmd": "DISPATCH", "evt": "READY"})
        while True:
            try:
                seen.append(frame(conn))
                send(conn, 1, {"cmd": "SET_ACTIVITY"})
            except (OSError, ValueError, struct.error):
                return
    threading.Thread(target=discord, daemon=True).start()

    st = discord_status.DiscordStatus(client_id="1234567890")
    st.set("Online co-op", "Castle: Tucker", party=(3, 4))
    for _ in range(50):
        if len(seen) >= 2:
            break
        time.sleep(0.1)
    check(seen and seen[0] == (0, {"v": 1, "client_id": "1234567890"}), "the handshake carries the app's client id")
    act = seen[1][1]["args"]["activity"] if len(seen) > 1 else {}
    check(seen[1][1]["cmd"] == "SET_ACTIVITY" if len(seen) > 1 else False, "then it sets the activity")
    check(act.get("details") == "Online co-op" and act.get("state") == "Castle: Tucker" and
          act.get("party", {}).get("size") == [3, 4] and act.get("timestamps", {}).get("start"),
          f"what's shown: how, the castle, the room's size, since when: {act}")
    st.set("In the menus")
    for _ in range(50):
        if len(seen) >= 3:
            break
        time.sleep(0.1)
    check(len(seen) >= 3 and seen[2][1]["args"]["activity"]["details"] == "In the menus", "and it follows the player")
    check(not any("BAT-" in json.dumps(f) for f in seen), "never a room code")
    st.close()
    check(discord_status.DiscordStatus(client_id="").enabled is False, "no client id: off")
    print(f"\n{'all passed' if not fails else f'{len(fails)} FAILED'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
