"""Two-game couch sessions and single-game online sessions: each game is a worker process with its
own SwanStation core and Host, linked over UDP.

    with Session(COOP_DISC, starts=("entrance", "entrance")) as s:
        a, b = s.step(60, p1=("right", ""))   # both games one frame at a time; returns snapshots
        s.a.read("g_CoopLink", ...)           # any Emu call on either game

Three or four starts (M17): every pair linked, each game with a Host per partner, keeping each
partner in its slot (link/mesh.py slot()). s.c, s.d are the third and fourth games.

The driver steps the games alternately, one frame each, so a presence sent at the end of A's
frame N is in B's mailbox before B's frame N+1 (and B's reaches A two frames later at most).
One libretro core per process, so each game is a worker process driven over a pipe.
"""

import multiprocessing as mp
import os
import sys
import traceback
import tempfile
from pathlib import Path

from coop_env import COOP, TOOLS, savestate

sys.path.insert(0, str(COOP))  # for `link`


class _Worker:
    """One game: its SwanStation core, Mailbox, Host and UDP transport, driven by commands
    (handle). A worker process runs one (_worker); Android, which can't start processes, runs one
    in its own process (InProcessGame, design/M9)."""

    def __init__(self, disc, start, rank, audio=False, shm_name=None, bind_host="127.0.0.1",
                 port=0, patch_crc=None, learn_peer=False, partners=1):
        import collections
        from emu import Emu
        from link.adapter import HarnessAdapter
        from link.host import Host
        from link.mailbox import Mailbox
        from link import portraits
        from link.transport import UdpTransport
        from module import symbols

        self.shm = None
        if shm_name:
            from multiprocessing import shared_memory
            self.shm = shared_memory.SharedMemory(name=shm_name)
        # The launcher (real-time play) booting from the disc: faster disc reads until the title
        self.emu = emu = Emu(disc, audio=audio, boot_speedup=bool(audio and not start))
        emu.__enter__()
        if start:  # a savestate library name, or a .state file (e.g. a launcher bookmark)
            emu.load_state_file(start if str(start).endswith(".state") else savestate(disc, start))
        self.mailbox = Mailbox(HarnessAdapter(emu), symbols()["g_CoopLink"])
        from link.partner_voices import PartnerVoices
        self.voices = PartnerVoices(self.mailbox.adapter, str(disc))  # #344: the partner's own sounds
        # Virtual time for the simulated internet (link/netsim.py): this game's frames / 60,
        # with the second game half a frame behind (the driver steps them alternately).
        # Real-time play (audio) keeps the wall clock.
        self.clock = {"t": rank / 120, "dt": 1 / 60}
        # M17: a Host per partner, each with its view of the mailbox (link/mailbox.py Partners)
        views = [self.mailbox]
        if partners > 1:
            from link.mailbox import Partners
            shared = Partners(self.mailbox)
            views = [shared.view(k) for k in range(partners)]
        self.transports, self.hosts = [], []
        for view in views:
            t = UdpTransport(port=port if not self.transports else 0, host="127.0.0.1", bind_host=bind_host)
            t.learn_peer = learn_peer
            if not audio and not os.environ.get("COOP_REALTIME"):
                t.clock = lambda: self.clock["t"]
            self.transports.append(t)
            self.hosts.append(Host(view, t, rank, patch_crc=patch_crc, playout=learn_peer))
        self.transport, self.host = self.transports[0], self.hosts[0]
        self.portraits = portraits.read(disc)
        for host in self.hosts:
            host.set_portraits(self.portraits)
        self.room = None  # M17 step 6: a Room's links instead, once "room" starts one
        self.host_settings = {}
        self.bind_host, self.patch_crc = bind_host, patch_crc
        self.fake_clock = not audio and not os.environ.get("COOP_REALTIME")
        self.linked = True
        self.host_ms = collections.deque(maxlen=3600)  # the host's time per frame (never waits)

    def handle(self, cmd, args):
        import time
        emu, host = self.emu, self.host
        if cmd == "step":
            n, p1 = args
            for _ in range(n):
                if self.linked:
                    self.link_before(p1)
                emu.step(1, p1)
                self.voice_frame(render=False)
                self.clock["t"] += self.clock["dt"]
                if self.linked:
                    t0 = time.perf_counter()
                    self.link_hosts()
                    self.host_ms.append((time.perf_counter() - t0) * 1000)
            return emu.snapshot()
        if cmd == "host_ms":
            out = list(self.host_ms)
            self.host_ms.clear()
            return out
        if cmd == "rate":  # this PC's frame rate (its clock drifts against the other's)
            self.clock["dt"] = 1 / args
        elif cmd == "stall":  # this PC hitches: time passes, the game doesn't run
            self.clock["t"] += args / 60
        elif cmd == "room":  # M17 step 6: 3-4 players from one room code (link/mesh.py Room)
            code, hosting, kw = args
            self.start_room(code, hosting, dict(kw))
        elif cmd == "room_status":  # the lobby, each frame before the game runs: handshakes too
            if self.room is None:
                return None
            if args:
                self.room.tick(game_running=False)
            return self.room.status()
        elif cmd == "control":  # joint saves with 3+ players (M17): to and from every partner's link
            return self.control(*args)
        elif cmd == "connect":
            self.transport.connect(args)
        elif cmd == "connect_k":  # M17: partner k's link
            k, port = args
            self.transports[k].connect(port)
        elif cmd == "partition":  # the network drops everything, both ways (every partner's)
            for t in self.transports:
                t.partitioned = args
        elif cmd == "partition_k":  # M17: only partner k's link
            k, on = args
            self.transports[k].partitioned = on
        elif cmd == "unlink":  # stop the host: as if the partner's side vanished
            self.linked = False
        elif cmd == "link":
            self.linked = True
        elif cmd == "call":  # any Emu, Mailbox, Host, or UdpTransport method
            target, name, a, kw = args
            if target == "host" and name in self.HOST_SETTINGS:  # every partner's link gets them (M17)
                self.host_settings[name] = (a, kw)
                for h in self.room.all_hosts() if self.room else ():
                    getattr(h, name)(*a, **kw)
            if target == "hosts":  # M17: every partner's Host, the same call
                return [getattr(h, name)(*a, **kw) for h in self.hosts]
            obj = {"emu": emu, "mailbox": self.mailbox, "host": host, "transport": self.transport,
                   "voices": self.voices}.get(target)
            if obj is None:  # "host1", "transport2": partner k's (M17)
                kind, k = target.rstrip("0123456789"), int(target[len(target.rstrip("0123456789")):])
                obj = {"host": self.hosts, "transport": self.transports}[kind][k]
            return getattr(obj, name)(*a, **kw)
        elif cmd == "suggest":  # the app's buttons changed while it waits for the next frame (rollback)
            if self.linked:
                self.link_before(args, suggest_only=True)
        elif cmd == "frame":  # real-time play: one frame, back with its picture and sound
            if self.linked:
                self.link_before(args)
            emu.step(1, args)
            if self.linked:
                self.link_frame()
            picture = emu.raw_frame()
            self.voice_frame()
            if picture and self.shm is not None:  # the pixels go through shared memory
                w, h, fmt, pitch, data = picture
                self.shm.buf[:len(data)] = data
                picture = (w, h, fmt, pitch, len(data))
            return picture, self.voices.mix(emu.take_audio())
        elif cmd == "screenshot":
            img = emu.screenshot()
            return None if img is None else (img.size, img.tobytes())
        elif cmd == "quit":
            self.close()
        else:
            raise ValueError(f"unknown command {cmd}")
        return None

    LINK_ERRORS_LOGGED = 5

    def link_frame(self):
        """The host's frame, in real-time play: whatever goes wrong in the link, the game runs on
        (the partner stalls, at worst), and the first few failures go to the worker's log, for F9
        reports. Tests step with "step", which raises."""
        try:
            self.link_hosts()
        except Exception:  # noqa: BLE001 - a player's session is worth more than the link's frame
            self.link_errors = getattr(self, "link_errors", 0) + 1
            if self.link_errors <= self.LINK_ERRORS_LOGGED:
                import logging
                logging.getLogger("link").exception("the host's frame failed (%d so far)", self.link_errors)

    HOST_SETTINGS = {"set_player", "set_mod", "set_castle", "set_rules", "set_fresh", "set_portraits", "set_hello",
                     "set_player_id"}

    def voice_frame(self, render=True):
        """The partner's sounds this game can't play (#344), after its frame: never in the frame's way."""
        try:
            self.voices.poll(render)
        except Exception:  # noqa: BLE001
            self.voice_errors = getattr(self, "voice_errors", 0) + 1

    def link_before(self, pad, suggest_only=False):
        """The buttons for the frame about to run, to every partner's host (rollback suggestions).
        Never in the way of the frame."""
        try:
            from emu import pad as as_mask
            from link.rollback import ps_buttons
            ps = ps_buttons(as_mask(pad))
            hosts = self.room.all_hosts() if self.room is not None else self.hosts
            for h in hosts:
                if suggest_only:
                    h.suggest(ps)
                else:
                    h.before_frame(ps)
        except Exception:  # noqa: BLE001 - a suggestion is only ever a guess
            self.suggest_errors = getattr(self, "suggest_errors", 0) + 1

    def link_hosts(self):
        if self.room is not None:
            self.room.tick(game_running=True)
        else:
            for h in self.hosts:
                h.after_frame()

    def control(self, what, msg=None, to=None):
        """send: a control message to partner `to` (a player number), or every partner; take: what
        came, as (player number, message); players: {number: {"pid", "slot"}} of the linked ones."""
        from link.mesh import slot
        room = self.room
        if what == "send":
            for n, h in (room.hosts.items() if room else ((1, self.host),)):
                if to is None or to == n:
                    h.send_control(msg)
            return None
        if what == "take":
            return [(n, m) for n, h in (room.hosts.items() if room else ((1, self.host),)) for m in h.take_control()]
        if what == "players":
            if room is None:
                return {1: {"pid": (self.host.partner_hello or {}).get("pid"), "slot": 0}}
            return {n: {"pid": (h.partner_hello or {}).get("pid"), "slot": slot(room.me, n)}
                    for n, h in room.hosts.items() if h.partner_hello and room.me is not None}
        raise ValueError(what)

    def start_room(self, code, hosting, kw):
        """From here on this game's partners are a Room's (link/mesh.py): player 0 hosting, or a
        joiner. The transport made at start is the first link (the LAN broadcast's port)."""
        from link.host import Host
        from link.mesh import Room
        from link.transport import UdpTransport
        first = [self.transport]

        def new_transport():
            t = first.pop() if first else UdpTransport(port=0, host="127.0.0.1", bind_host=self.bind_host)
            if t not in self.transports:
                self.transports.append(t)
            if self.fake_clock:
                t.clock = lambda: self.clock["t"]
            return t

        def make_host(view, t, rank):
            h = Host(view, t, rank, patch_crc=self.patch_crc, playout=True)
            h.set_portraits(self.portraits)
            for name, (a, k) in self.host_settings.items():
                getattr(h, name)(*a, **k)
            return h
        self.hosts = []
        self.room = Room(self.mailbox, code, hosting, new_transport, make_host=make_host, **kw)
        self.host = (self.room.all_hosts() or [self.host])[0]

    def close(self):
        if self.linked and self.room is not None:
            self.room.goodbye()
        if self.linked:
            for h in self.hosts:
                h.goodbye()
        for t in self.transports:
            t.close()
        self.emu.__exit__(None, None, None)


def _worker(conn, disc, start, rank, audio=False, shm_name=None, bind_host="127.0.0.1",
            port=0, patch_crc=None, learn_peer=False, partners=1):
    import faulthandler  # a native crash (the emulator's) writes its stack where the proxy finds it
    faulthandler.enable(open(Path(tempfile.gettempdir()) / f"coop-worker-{os.getpid()}.txt", "w"))
    if os.environ.get("COOP_WORKER_LOG"):  # the launcher's: a worker's warnings (connect, relay) kept
        import logging
        logging.basicConfig(filename=os.environ["COOP_WORKER_LOG"], level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        w = _Worker(disc, start, rank, audio, shm_name, bind_host, port, patch_crc, learn_peer, partners)
        conn.send(("ok", w.transport.port if partners == 1 else [t.port for t in w.transports]))
        while True:
            cmd, args = conn.recv()
            try:
                value = w.handle(cmd, args)
            except Exception:
                conn.send(("error", traceback.format_exc()))
                continue
            conn.send(("ok", value))
            if cmd == "quit":
                return
    except Exception:
        conn.send(("error", traceback.format_exc()))


class Game:
    """Proxy to one worker: any Emu method by name, plus link/mailbox/transport helpers."""

    def __init__(self, name, conn, proc):
        self.name, self.conn, self.proc = name, conn, proc

    def _ask(self, cmd, args=None):
        self.conn.send((cmd, args))
        try:
            status, value = self.conn.recv()
        except EOFError:  # its process died: say how (a negative code is the signal), and where
            self.proc.join(2)
            trace = Path(tempfile.gettempdir()) / f"coop-worker-{self.proc.pid}.txt"
            where = trace.read_text()[-1500:] if trace.exists() else ""
            raise RuntimeError(f"game {self.name}'s process died (exit code {self.proc.exitcode}) during {cmd}\n{where}")
        if status != "ok":
            raise RuntimeError(f"game {self.name}: {value}")
        return value

    def step(self, n=1, p1=0):
        return self._ask("step", (n, p1))

    def frame(self, pad=0):
        """One frame with this pad: ((w, h, mode, pixels) or None, audio bytes). With shared
        memory, pixels is the byte count in self.shm instead."""
        return self._ask("frame", pad)

    def suggest(self, pad=0):
        """The player's buttons changed between frames (online): to the partners now."""
        return self._ask("suggest", pad)

    def frame_start(self, pad=0):
        """frame(), split in two so both games can run their frame at the same time."""
        self.conn.send(("frame", pad))

    def frame_end(self):
        status, value = self.conn.recv()
        if status != "ok":
            raise RuntimeError(f"game {self.name}: {value}")
        return value

    def mailbox(self, name, *a, **kw):
        return self._ask("call", ("mailbox", name, a, kw))

    def host(self, name, *a, **kw):
        return self._ask("call", ("host", name, a, kw))

    def voices(self, name, *a, **kw):
        """The partner's sounds this game hands to its host (link/partner_voices.py, #344)."""
        return self._ask("call", ("voices", name, a, kw))

    def room_status(self, tick=False):
        """3+ players (M17): the game's room, or None when it has a single partner's link."""
        return self._ask("room_status", tick)

    def transport(self, name, *a, **kw):
        return self._ask("call", ("transport", name, a, kw))

    def unlink(self):
        return self._ask("unlink")

    def partition(self, on=True):
        return self._ask("partition", on)

    def link(self):
        return self._ask("link")

    def host_ms(self):
        """The host's milliseconds per frame since last asked."""
        return self._ask("host_ms")

    def set_rate(self, fps):
        return self._ask("rate", fps)

    def stall(self, frames):
        return self._ask("stall", frames)

    def screenshot(self):
        from PIL import Image
        shot = self._ask("screenshot")
        return None if shot is None else Image.frombytes("RGB", *shot)

    def __getattr__(self, name):  # Emu methods: read, write, snapshot, save_state, ...
        return lambda *a, **kw: self._ask("call", ("emu", name, a, kw))


class InProcessGame(Game):
    """A Game whose worker runs here, in this process (Android: design/M9)."""

    def __init__(self, name, worker):
        self.name, self.w, self.proc, self.shm = name, worker, None, None
        self._pending = None

    def _ask(self, cmd, args=None):
        return self.w.handle(cmd, args)

    def frame_start(self, pad=0):
        self._pending = self.w.handle("frame", pad)

    def frame_end(self):
        value, self._pending = self._pending, None
        return value


class MailboxProxy:
    """A worker game's Mailbox, for code that wants one (link.jointsave)."""

    def __init__(self, game):
        self.game = game

    def __getattr__(self, name):
        return lambda *a: self.game.mailbox(name, *a)


class CrashGuard:
    """Fails a test the moment a game's exception vector changes: a write through a bad pointer
    (the 0.13 playtest's freeze) leaves the CPU looping there while the emulator runs on, and the
    test only sees a game that stopped moving, if it looks at all. A game spinning in its own code
    leaves the vector alone, so the game's timer must move too. Read every second of play."""

    VECTOR, SIZE, EVERY, HUNG, GAME_ENDING = 0x80000080, 16, 60, 1200, 9

    def __init__(self):
        self.good, self.frames, self.beats = {}, 0, {}

    def check(self, games):
        self.frames += 1
        if self.frames % self.EVERY == 1:
            for g in games:
                now = g.read_bytes(self.VECTOR, self.SIZE)
                if self.good.setdefault(g.name, now) != now:
                    raise RuntimeError(f"game {g.name} crashed: its exception vector was overwritten "
                                       f"by frame {self.frames} ({now.hex()})")
                beat = g.read("g_Timer")
                last = self.beats.get(g.name)
                # The ending's movie plays in a loop of its own, outside MainGame and its timer.
                if last is None or last[0] != beat or g.read("g_GameState") == self.GAME_ENDING:
                    self.beats[g.name] = (beat, self.frames)
                elif beat and self.frames - last[1] >= self.HUNG:
                    for h in games:  # for reading where it stopped: see docs/research.md
                        h.save_state_file(str(TOOLS["out"] / f"hung_{h.name}.state"))
                    raise RuntimeError(f"game {g.name} hung: its timer stopped at frame {last[1]}")


class HostProxy:
    """A worker game's Host, for online JointSave control messages."""

    def __init__(self, game):
        self.game = game

    def __getattr__(self, name):
        return lambda *a, **kw: self.game.host(name, *a, **kw)


class RoomProxy:
    """A worker game's room, for JointSave with 3+ players (M17): control messages to and from
    each partner by player number."""

    def __init__(self, game):
        self.game = game

    def send(self, msg, to=None):
        self.game._ask("control", ("send", msg, to))

    def take(self):
        return self.game._ask("control", ("take",))

    def players(self):
        return self.game._ask("control", ("players",))


class Session:
    def __init__(self, disc, starts=("entrance", "entrance"), session_file=None, audio=False,
                 characters=None, blob=None):
        """disc: one disc for every game, or one each. starts: one per game (two, or three or four:
        M17). session_file: run the couch launcher's joint saves (link.jointsave) into that file,
        every frame (two games). audio: keep sound (the launcher). characters: each game's CHAR_*
        (design/M8), from its next load. blob: Maria's (launcher/characters.py), for every game, if
        any plays her."""
        self.disc, self.starts, self.session_file, self.audio = disc, starts, session_file, audio
        self.characters, self.blob = characters or (0,) * len(starts), blob
        self.joint = None
        self.guard = CrashGuard()

    def __enter__(self):
        ctx = mp.get_context("spawn")
        self.games = []
        n = len(self.starts)
        discs = self.disc if isinstance(self.disc, (tuple, list)) else (self.disc,) * n
        self._shms = []
        for i, start in enumerate(self.starts):
            shm_name = None
            if self.audio:  # real-time play: frames through shared memory (640x480x4 at most)
                from multiprocessing import shared_memory
                shm = shared_memory.SharedMemory(create=True, size=640 * 480 * 4)
                self._shms.append(shm)
                shm_name = shm.name
            parent, child = ctx.Pipe()
            proc = ctx.Process(target=_worker, daemon=True,
                               args=(child, str(discs[i]), start, i, self.audio, shm_name),
                               kwargs={"partners": n - 1})
            proc.start()
            game = Game("ABCD"[i], parent, proc)
            game.shm = self._shms[-1] if shm_name else None
            self.games.append(game)
        ports = []
        for g in self.games:
            status, value = g.conn.recv()
            if status != "ok":
                raise RuntimeError(f"game {g.name} failed to start: {value}")
            ports.append(value)
        self.a, self.b = self.games[:2]
        self.c = self.games[2] if n > 2 else None
        self.d = self.games[3] if n > 3 else None
        if n == 2:
            self.a._ask("connect", ports[1])
            self.b._ask("connect", ports[0])
        else:  # M17: every pair, each in the other's slot
            from link.mesh import slot
            for i in range(n):
                for j in range(n):
                    if i != j:
                        self.games[i]._ask("connect_k", (slot(i, j), ports[j][slot(j, i)]))
        for g, c in zip(self.games, self.characters):
            g._ask("call", ("hosts", "set_player", (), {"character": c, "blob": self.blob}))
        if os.environ.get("COOP_BODY_OFF"):  # M13: no partner body in either game (comparisons)
            from module import symbols
            for g in self.games:
                g.write(symbols()["g_CoopBodyOff"], 1)
        if self.session_file:
            from link.jointsave import JointSave
            self.joint = JointSave([MailboxProxy(self.a), MailboxProxy(self.b)], self.session_file)
        return self

    def set_net(self, profile, seed=1, **overrides):
        """Both directions through a simulated internet (link/netsim.py), seeded per direction."""
        for i, g in enumerate(self.games):
            g.transport("set_netsim", profile, seed * 2 + i, **overrides)
            g.host("set_playout", bool(profile))

    def step(self, n=1, p1=None, each=None):
        """Steps every game n frames, one frame each in turn. p1 is (pad A, pad B, ...), or a
        function (frame index, snapshot A, snapshot B, ...) -> pads. each(i, sa, sb, ...) is
        called after every frame. Returns the last snapshots, one per game."""
        snaps = [None] * len(self.games)
        for i in range(n):
            pads = p1(i, *snaps) if callable(p1) else (p1 or ("",) * len(self.games))
            snaps = [g.step(1, pad) for g, pad in zip(self.games, pads)]
            if self.joint:
                self.joint.tick()
            self.guard.check(self.games)
            if each:
                each(i, *snaps)
        return tuple(snaps)

    def __exit__(self, *exc):
        for g in self.games:
            if g.proc.is_alive():
                try:
                    g._ask("quit")
                except (RuntimeError, EOFError, BrokenPipeError):
                    pass
            g.proc.join(timeout=10)
            if g.proc.is_alive():
                g.proc.kill()
        for shm in getattr(self, "_shms", []):
            try:
                shm.close()
                shm.unlink()
            except BufferError:  # something still borrows it; the OS frees it at exit
                pass


class OnlineSession:
    """One local game instance per player (design/M7, D74), connected to a remote partner over UDP."""

    def __init__(self, disc, start=None, rank=0, peer=None, session_file=None, audio=False,
                 bind_host="0.0.0.0", port=0, patch_crc=None, learn_peer=True, character=0, blob=None,
                 in_process=False, joint=False, mod=None):
        """in_process: run the game here, not in a worker process (Android: design/M9). joint:
        joint saves even before the castle's file is known (an online joiner: design/M11). mod: the
        randomizer seed the disc was made from, in words (HELO's "mod", design/M20-randomizer.md)."""
        self.disc, self.start, self.rank, self.character, self.blob = disc, start, rank, character, blob
        self.in_process = in_process
        self.peer, self.session_file, self.audio = peer, session_file, audio
        self.bind_host, self.req_port = bind_host, port
        self.patch_crc, self.learn_peer = patch_crc, learn_peer
        self.mod = mod
        self.joint = None
        self.want_joint = joint
        self.port = None
        self.guard = CrashGuard()

    def __enter__(self):
        self._shms = []
        if self.in_process:
            w = _Worker(str(self.disc), self.start, self.rank, self.audio, None, self.bind_host,
                        self.req_port, self.patch_crc, self.learn_peer)
            return self._started(InProcessGame("ABCD"[self.rank], w), w.transport.port)
        ctx = mp.get_context("spawn")
        shm_name = None
        if self.audio:
            from multiprocessing import shared_memory
            shm = shared_memory.SharedMemory(create=True, size=640 * 480 * 4)
            self._shms.append(shm)
            shm_name = shm.name
        parent, child = ctx.Pipe()
        proc = ctx.Process(
            target=_worker, daemon=True,
            args=(child, str(self.disc), self.start, self.rank, self.audio, shm_name,
                  self.bind_host, self.req_port, self.patch_crc, self.learn_peer),
        )
        proc.start()
        game = Game("ABCD"[self.rank], parent, proc)
        game.shm = self._shms[-1] if shm_name else None
        status, value = game.conn.recv()
        if status != "ok":
            raise RuntimeError(f"online game failed to start: {value}")
        return self._started(game, value)

    def _started(self, game, port):
        self.port = port
        self.games = [game]
        self.local = self.a = game
        self.b = None
        game.host("set_player", character=self.character, blob=self.blob)
        if self.mod:
            game.host("set_mod", self.mod)
        if self.peer is not None:
            self.connect(self.peer)
        if self.session_file or self.want_joint:
            from link.jointsave import JointSave
            self.joint = JointSave([MailboxProxy(game)], self.session_file,
                                   host=HostProxy(game), rank=self.rank)
        return self

    def connect(self, peer):
        self.peer = peer
        self.local._ask("connect", peer)

    def start_room(self, code, hosting, pid=None, **kw):
        """3+ players (M17 step 6): join or host a room of up to four by its code (link/mesh.py).
        pid: this player's lasting id (their castle slot follows it)."""
        if pid:
            self.local.host("set_player_id", pid)
        self.local._ask("room", (code, hosting, kw))
        self.room_on = True
        if self.joint is not None:
            self.joint.room = RoomProxy(self.local)
            self.joint.pid = pid

    def room_status(self, tick=True):
        """The room: this game's number, who's in, each partner's link. tick: also run the
        handshakes (the lobby, before the game runs)."""
        return self.local._ask("room_status", tick)

    def step(self, n=1, pad="", each=None):
        s = None
        for i in range(n):
            p = pad(i, s) if callable(pad) else pad
            s = self.local.step(1, p)
            if self.joint:
                self.joint.tick()
            self.guard.check([self.local])
            if each:
                each(i, s)
        return s

    def __exit__(self, *exc):
        if self.in_process:
            self.local.w.close()
            return
        Session.__exit__(self, *exc)


# --- scenarios -------------------------------------------------------------------------------

SESSION_SCENARIOS = {}


def session_scenario(starts=("entrance", "entrance"), discs=None, characters=None, full=False):
    """Like scenario.scenario, for two linked games (or three or four: one start each, M17). discs
    defaults to the co-op disc for each. characters: each game's CHAR_* (design/M8), from its next
    load. full: only in the full suite."""
    def register(fn):
        from scenario import FULL_ONLY
        SESSION_SCENARIOS[fn.__name__] = (fn, starts, discs, characters)
        if full:
            FULL_ONLY.add(fn.__name__)
        return fn
    return register


class SessionRun:
    """What a session scenario gets: the session, expect(), and side-by-side GIF evidence."""

    def __init__(self, session, name, gif_every=12):
        self.s, self.name = session, name
        self.checks, self._frames, self._gif_every, self._n = [], [], gif_every, 0

    def step(self, n=1, p1=None, each=None):
        def after(i, *snaps):
            self._n += 1
            if self._n % self._gif_every == 0:
                self.capture()
            if each:
                each(i, *snaps)
        return self.s.step(n, p1, after)

    def capture(self):
        from PIL import Image
        if not all(g.proc.is_alive() for g in self.s.games):  # e.g. stale_link killed one
            return
        shots = [g.screenshot() for g in self.s.games]
        if all(shots):
            frame = Image.new("RGB", (sum(x.width for x in shots) + 4 * (len(shots) - 1), max(x.height for x in shots)),
                              "white")
            x = 0
            for shot in shots:
                frame.paste(shot, (x, 0))
                x += shot.width + 4
            self._frames.append(frame.resize((frame.width * 3 // 4, frame.height * 3 // 4)))

    def expect(self, ok, what, **details):
        from scenario import Failed
        self.checks.append({"ok": bool(ok), "what": what, **details})
        if not ok:
            raise Failed(f"{what} {details}")

    def save_gif(self, path):
        if self._frames:
            self._frames[0].save(path, save_all=True, append_images=self._frames[1:],
                                 duration=self._gif_every * 1000 // 60, loop=0, optimize=True)


def run_session_scenario(name):
    import json
    import time
    from scenario import Failed
    from module import COOP_DISC

    fn, starts, discs, characters = SESSION_SCENARIOS[name]
    out = TOOLS["out"] / name
    out.mkdir(parents=True, exist_ok=True)
    t0, error = time.time(), None
    run = None
    try:
        blob = None
        if {2, 3, 4, 5} & set(characters or ()):  # the blob characters (the Marias, Ultimate Richter)
            from module import maria_blob
            blob = maria_blob()
        with Session(discs or COOP_DISC, starts, characters=characters, blob=blob) as s:
            run = SessionRun(s, name)
            try:
                fn(run)
            except Failed as exc:
                error = f"assertion failed: {exc}"
            run.capture()
            run.save_gif(out / "clip.gif")
    except Exception:
        error = traceback.format_exc()
    report = {"scenario": name, "starts": list(starts), "passed": error is None, "error": error,
              "seconds": round(time.time() - t0, 1), "checks": run.checks if run else []}
    (out / "report.json").write_text(json.dumps(report, indent=1))
    return report
