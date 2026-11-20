"""Rejoining a room (#318), no games run: a castle keeps its room code while it's recent, so a
partner who dropped out rejoins with the code they have, and Join offers the last room it joined.

    python launcher/test_rejoin.py
"""
import os
import sys
import tempfile
import time
import types
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]

failures = []


def check(ok, what):
    print(("ok   " if ok else "FAIL ") + what)
    if not ok:
        failures.append(what)


def main():
    with tempfile.TemporaryDirectory() as d:
        os.environ["COOP_DATA"] = d
        import app
        from archive import Castle
        codes = iter(["BAT-AAAA", "BAT-BBBB", "BAT-CCCC"])
        make = lambda: next(codes)  # noqa: E731
        me = types.SimpleNamespace(settings={})
        room = lambda c: app.Launcher.castle_room(me, c, make)  # noqa: E731
        a, b = Castle.new(name="A"), Castle.new(name="B")
        first = room(a)
        check(first == "BAT-AAAA" and Castle(a.dir).info["room"]["code"] == first, "a castle hosted: a new code, kept with it")
        check(room(Castle(a.dir)) == first, "hosted again soon: the same code, so the partner rejoins with theirs")
        check(room(b) == "BAT-BBBB", "another castle: its own code")
        a.info["room"]["at"] = time.time() - app.REJOIN_S - 1
        a.save_info()
        check(room(Castle(a.dir)) == "BAT-CCCC", "hosted again much later: a new code")
        a.info["room"] = "junk"
        check(isinstance(app.Launcher.castle_room(me, a, lambda: "BAT-DDDD"), str), "a castle's junk room: a new code")

        last = lambda: app.Launcher.last_room(me)  # noqa: E731
        check(last() == "", "never joined: no Rejoin")
        me.settings["last_room"] = {"code": "CAT-7K2Q", "at": time.time()}
        check(last() == "CAT-7K2Q", "joined a room: Rejoin offers it")
        me.settings["last_room"]["at"] = time.time() - app.REJOIN_S - 1
        check(last() == "", "long ago: no Rejoin")
        me.settings["last_room"] = ["junk"]
        check(last() == "", "junk in the settings: no Rejoin")
    # #326: the host is shown its address, for a partner to Join by ip:port
    import app
    import link.rendezvous as rv
    rv_local = rv.local_ip
    rv.local_ip = lambda: "192.168.1.20"
    fake = types.SimpleNamespace(hosting_session=types.SimpleNamespace(
        port=47811, room_on=True, room_status=lambda tick: {"waiting": {"mine": [["192.168.1.20", 47811], ["93.184.216.34", 40001]]}}))
    got = app.Launcher.host_addresses(fake)
    check(got == ("192.168.1.20:47811", "93.184.216.34:40001"), f"hosting: the LAN ip:port and, once STUN found it, the internet one ({got})")
    fake.host_addresses = lambda: got
    info = app.Launcher.address_info(fake)
    check("192.168.1.20:47811" in info and "93.184.216.34:40001" in info, "Help › About says them")
    fake.hosting_session = None
    check(app.Launcher.host_addresses(fake) is None, "not hosting: nothing")
    rv.local_ip = rv_local
    print(f"\n{'all passed' if not failures else f'{len(failures)} FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

