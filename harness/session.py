"""Two-game couch sessions and single-game online sessions: each game is a worker process with its
own SwanStation core and Host, linked over UDP.

    with Session(COOP_DISC, starts=("entrance", "entrance")) as s:
        a, b = s.step(60, p1=("right", ""))   # both games one frame at a time; returns snapshots
        s.a.read("g_CoopLink", ...)           # any Emu call on either game

The driver steps the games alternately, one frame each, so a presence sent at the end of A's
frame N is in B's mailbox before B's frame N+1 (and B's reaches A two frames later at most).
One libretro core per process, so each game is a worker process driven over a pipe.
"""

import multiprocessing as mp
import os
import sys
import traceback

from coop_env import COOP, TOOLS, savestate

sys.path.insert(0, str(COOP))  # for `link`


class _Worker:
    """One game: its SwanStation core, Mailbox, Host and UDP transport, driven by commands
    (handle). A worker process runs one (_worker); Android, which can't start processes, runs one
    in its own process (InProcessGame, design/M9)."""

    def __init__(self, disc, start, rank, audio=False, shm_name=None, bind_host="127.0.0.1",
                 port=0, patch_crc=None, learn_peer=False):
        import collections
        from emu import Emu
        from link.adapter import HarnessAdapter
        from link.host import Host
        from link.mailbox import Mailbox
        from link.transport import UdpTransport
        from module import symbols

        self.shm = None
        if shm_name:
            from multiprocessing import shared_memory
            self.shm = shared_memory.SharedMemory(name=shm_name)
        self.emu = emu = Emu(disc, audio=audio)
        emu.__enter__()
        if start:  # a savestate library name, or a .state file (e.g. a launcher bookmark)
            emu.load_state_file(start if str(start).endswith(".state") else savestate(disc, start))
        self.mailbox = Mailbox(HarnessAdapter(emu), symbols()["g_CoopLink"])
        self.transport = UdpTransport(port=port, host="127.0.0.1", bind_host=bind_host)
        self.transport.learn_peer = learn_peer
        # Virtual time for the simulated internet (link/netsim.py): this game's frames / 60,
        # with the second game half a frame behind (the driver steps them alternately).
        # Real-time play (audio) keeps the wall clock.
        self.clock = {"t": rank / 120, "dt": 1 / 60}
        if not audio:
            self.transport.clock = lambda: self.clock["t"]
        self.host = Host(self.mailbox, self.transport, rank, patch_crc=patch_crc, playout=learn_peer)
        self.linked = True
        self.host_ms = collections.deque(maxlen=3600)  # the host's time per frame (never waits)

    def handle(self, cmd, args):
        import time
        emu, host = self.emu, self.host
        if cmd == "step":
            n, p1 = args
            for _ in range(n):
                emu.step(1, p1)
                self.clock["t"] += self.clock["dt"]
                if self.linked:
                    t0 = time.perf_counter()
                    host.after_frame()
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
        elif cmd == "connect":
            self.transport.connect(args)
        elif cmd == "partition":  # the network drops everything, both ways
            self.transport.partitioned = args
        elif cmd == "unlink":  # stop the host: as if the partner's side vanished
            self.linked = False
        elif cmd == "link":
            self.linked = True
        elif cmd == "call":  # any Emu, Mailbox, Host, or UdpTransport method
            target, name, a, kw = args
            obj = {"emu": emu, "mailbox": self.mailbox, "host": host, "transport": self.transport}[target]
            return getattr(obj, name)(*a, **kw)
        elif cmd == "frame":  # real-time play: one frame, back with its picture and sound
            emu.step(1, args)
            if self.linked:
                host.after_frame()
            picture = emu.raw_frame()
            if picture and self.shm is not None:  # the pixels go through shared memory
                w, h, fmt, pitch, data = picture
                self.shm.buf[:len(data)] = data
                picture = (w, h, fmt, pitch, len(data))
            return picture, emu.take_audio()
        elif cmd == "screenshot":
            img = emu.screenshot()
            return None if img is None else (img.size, img.tobytes())
        elif cmd == "quit":
            self.close()
        else:
            raise ValueError(f"unknown command {cmd}")
        return None

    def close(self):
        if self.linked:
            self.host.goodbye()
        self.transport.close()
        self.emu.__exit__(None, None, None)


def _worker(conn, disc, start, rank, audio=False, shm_name=None, bind_host="127.0.0.1",
            port=0, patch_crc=None, learn_peer=False):
    if os.environ.get("COOP_WORKER_LOG"):  # the launcher's: a worker's warnings (connect, relay) kept
        import logging
        logging.basicConfig(filename=os.environ["COOP_WORKER_LOG"], level=logging.INFO,
                            format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        w = _Worker(disc, start, rank, audio, shm_name, bind_host, port, patch_crc, learn_peer)
        conn.send(("ok", w.transport.port))
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
        status, value = self.conn.recv()
        if status != "ok":
            raise RuntimeError(f"game {self.name}: {value}")
        return value

    def step(self, n=1, p1=0):
        return self._ask("step", (n, p1))

    def frame(self, pad=0):
        """One frame with this pad: ((w, h, mode, pixels) or None, audio bytes). With shared
        memory, pixels is the byte count in self.shm instead."""
        return self._ask("frame", pad)

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


class HostProxy:
    """A worker game's Host, for online JointSave control messages."""

    def __init__(self, game):
        self.game = game

    def __getattr__(self, name):
        return lambda *a, **kw: self.game.host(name, *a, **kw)


class Session:
    def __init__(self, disc, starts=("entrance", "entrance"), session_file=None, audio=False,
                 characters=(0, 0), blob=None):
        """disc: one disc for both games, or (disc A, disc B). session_file: run the couch
        launcher's joint saves (link.jointsave) into that file, every frame. audio: keep sound
        (the launcher). characters: each game's CHAR_* (design/M8), from its next load. blob:
        Maria's (launcher/characters.py), for both games, if either plays her."""
        self.disc, self.starts, self.session_file, self.audio = disc, starts, session_file, audio
        self.characters, self.blob = characters, blob
        self.joint = None

    def __enter__(self):
        ctx = mp.get_context("spawn")
        self.games = []
        discs = self.disc if isinstance(self.disc, (tuple, list)) else (self.disc, self.disc)
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
                               args=(child, str(discs[i]), start, i, self.audio, shm_name))
            proc.start()
            game = Game("AB"[i], parent, proc)
            game.shm = self._shms[-1] if shm_name else None
            self.games.append(game)
        ports = []
        for g in self.games:
            status, value = g.conn.recv()
            if status != "ok":
                raise RuntimeError(f"game {g.name} failed to start: {value}")
            ports.append(value)
        self.a, self.b = self.games
        self.a._ask("connect", ports[1])
        self.b._ask("connect", ports[0])
        for g, c in zip(self.games, self.characters):
            g.host("set_player", character=c, blob=self.blob)
        if self.session_file:
            from link.jointsave import JointSave
            self.joint = JointSave([MailboxProxy(self.a), MailboxProxy(self.b)], self.session_file)
        return self

    def set_net(self, profile, seed=1, **overrides):
        """Both directions through a simulated internet (link/netsim.py), seeded per direction."""
        for i, g in enumerate(self.games):
            g.transport("set_netsim", profile, seed * 2 + i, **overrides)
            g.host("set_playout", bool(profile))

    def step(self, n=1, p1=("", ""), each=None):
        """Steps both games n frames, alternating one frame each. p1 is (pad A, pad B), or a
        function (frame index, snapshot A, snapshot B) -> (pad A, pad B). each(i, sa, sb) is
        called after every frame. Returns the last pair of snapshots."""
        sa = sb = None
        for i in range(n):
            pa, pb = p1(i, sa, sb) if callable(p1) else p1
            sa = self.a.step(1, pa)
            sb = self.b.step(1, pb)
            if self.joint:
                self.joint.tick()
            if each:
                each(i, sa, sb)
        return sa, sb

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
                 in_process=False, joint=False):
        """in_process: run the game here, not in a worker process (Android: design/M9). joint:
        joint saves even before the castle's file is known (an online joiner: design/M11)."""
        self.disc, self.start, self.rank, self.character, self.blob = disc, start, rank, character, blob
        self.in_process = in_process
        self.peer, self.session_file, self.audio = peer, session_file, audio
        self.bind_host, self.req_port = bind_host, port
        self.patch_crc, self.learn_peer = patch_crc, learn_peer
        self.joint = None
        self.want_joint = joint
        self.port = None

    def __enter__(self):
        self._shms = []
        if self.in_process:
            w = _Worker(str(self.disc), self.start, self.rank, self.audio, None, self.bind_host,
                        self.req_port, self.patch_crc, self.learn_peer)
            return self._started(InProcessGame("AB"[self.rank], w), w.transport.port)
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
        game = Game("AB"[self.rank], parent, proc)
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

    def step(self, n=1, pad="", each=None):
        s = None
        for i in range(n):
            p = pad(i, s) if callable(pad) else pad
            s = self.local.step(1, p)
            if self.joint:
                self.joint.tick()
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


def session_scenario(starts=("entrance", "entrance"), discs=None, characters=(0, 0)):
    """Like scenario.scenario, for two linked games. discs defaults to the co-op disc twice.
    characters: each game's CHAR_* (design/M8), from its next load."""
    def register(fn):
        SESSION_SCENARIOS[fn.__name__] = (fn, starts, discs, characters)
        return fn
    return register


class SessionRun:
    """What a session scenario gets: the session, expect(), and side-by-side GIF evidence."""

    def __init__(self, session, name, gif_every=12):
        self.s, self.name = session, name
        self.checks, self._frames, self._gif_every, self._n = [], [], gif_every, 0

    def step(self, n=1, p1=("", ""), each=None):
        def after(i, sa, sb):
            self._n += 1
            if self._n % self._gif_every == 0:
                self.capture()
            if each:
                each(i, sa, sb)
        return self.s.step(n, p1, after)

    def capture(self):
        from PIL import Image
        if not all(g.proc.is_alive() for g in self.s.games):  # e.g. stale_link killed one
            return
        a, b = self.s.a.screenshot(), self.s.b.screenshot()
        if a and b:
            frame = Image.new("RGB", (a.width + 4 + b.width, max(a.height, b.height)), "white")
            frame.paste(a, (0, 0))
            frame.paste(b, (a.width + 4, 0))
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
        if 2 in characters:  # CHAR_MARIA
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
