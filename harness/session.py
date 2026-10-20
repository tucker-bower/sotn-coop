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
import sys
import traceback

from coop_env import COOP, TOOLS, savestate

sys.path.insert(0, str(COOP))  # for `link`


def _worker(conn, disc, start, rank, audio=False, shm_name=None, bind_host="127.0.0.1",
            port=0, patch_crc=None, learn_peer=False):
    from emu import Emu
    from link.adapter import HarnessAdapter
    from link.host import Host
    from link.mailbox import Mailbox
    from link.transport import UdpTransport
    from module import symbols

    shm = None
    if shm_name:
        from multiprocessing import shared_memory
        shm = shared_memory.SharedMemory(name=shm_name)
    try:
        with Emu(disc, audio=audio) as emu:
            if start:  # a savestate library name, or a .state file (e.g. a launcher bookmark)
                emu.load_state_file(start if str(start).endswith(".state") else savestate(disc, start))
            mailbox = Mailbox(HarnessAdapter(emu), symbols()["g_CoopLink"])
            transport = UdpTransport(port=port, host="127.0.0.1", bind_host=bind_host)
            transport.learn_peer = learn_peer
            host = Host(mailbox, transport, rank, patch_crc=patch_crc)
            linked = True
            conn.send(("ok", transport.port))
            while True:
                cmd, args = conn.recv()
                if cmd == "step":
                    n, p1 = args
                    for _ in range(n):
                        emu.step(1, p1)
                        if linked:
                            host.after_frame()
                    conn.send(("ok", emu.snapshot()))
                elif cmd == "connect":
                    transport.connect(args)
                    conn.send(("ok", None))
                elif cmd == "partition":  # the network drops everything, both ways
                    transport.partitioned = args
                    conn.send(("ok", None))
                elif cmd == "unlink":  # stop the host: as if the partner's side vanished
                    linked = False
                    conn.send(("ok", None))
                elif cmd == "link":
                    linked = True
                    conn.send(("ok", None))
                elif cmd == "call":  # any Emu, Mailbox, Host, or UdpTransport method
                    target, name, a, kw = args
                    obj = {"emu": emu, "mailbox": mailbox, "host": host, "transport": transport}[target]
                    conn.send(("ok", getattr(obj, name)(*a, **kw)))
                elif cmd == "frame":  # real-time play: one frame, back with its picture and sound
                    emu.step(1, args)
                    if linked:
                        host.after_frame()
                    picture = emu.raw_frame()
                    if picture and shm is not None:  # the pixels go through shared memory
                        w, h, fmt, pitch, data = picture
                        shm.buf[:len(data)] = data
                        picture = (w, h, fmt, pitch, len(data))
                    conn.send(("ok", (picture, emu.take_audio())))
                elif cmd == "screenshot":
                    img = emu.screenshot()
                    conn.send(("ok", None if img is None else (img.size, img.tobytes())))
                elif cmd == "quit":
                    transport.close()
                    conn.send(("ok", None))
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

    def screenshot(self):
        from PIL import Image
        shot = self._ask("screenshot")
        return None if shot is None else Image.frombytes("RGB", *shot)

    def __getattr__(self, name):  # Emu methods: read, write, snapshot, save_state, ...
        return lambda *a, **kw: self._ask("call", ("emu", name, a, kw))


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
    def __init__(self, disc, starts=("entrance", "entrance"), session_file=None, audio=False):
        """disc: one disc for both games, or (disc A, disc B). session_file: run the couch
        launcher's joint saves (link.jointsave) into that file, every frame. audio: keep sound
        (the launcher)."""
        self.disc, self.starts, self.session_file, self.audio = disc, starts, session_file, audio
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
        if self.session_file:
            from link.jointsave import JointSave
            self.joint = JointSave([MailboxProxy(self.a), MailboxProxy(self.b)], self.session_file)
        return self

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
                 bind_host="0.0.0.0", port=0, patch_crc=None, learn_peer=True):
        self.disc, self.start, self.rank = disc, start, rank
        self.peer, self.session_file, self.audio = peer, session_file, audio
        self.bind_host, self.req_port = bind_host, port
        self.patch_crc, self.learn_peer = patch_crc, learn_peer
        self.joint = None
        self.port = None

    def __enter__(self):
        ctx = mp.get_context("spawn")
        self._shms = []
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
        self.port = value
        self.games = [game]
        self.local = self.a = game
        self.b = None
        if self.peer is not None:
            self.connect(self.peer)
        if self.session_file:
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
        Session.__exit__(self, *exc)


# --- scenarios -------------------------------------------------------------------------------

SESSION_SCENARIOS = {}


def session_scenario(starts=("entrance", "entrance"), discs=None):
    """Like scenario.scenario, for two linked games. discs defaults to the co-op disc twice."""
    def register(fn):
        SESSION_SCENARIOS[fn.__name__] = (fn, starts, discs)
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

    fn, starts, discs = SESSION_SCENARIOS[name]
    out = TOOLS["out"] / name
    out.mkdir(parents=True, exist_ok=True)
    t0, error = time.time(), None
    run = None
    try:
        with Session(discs or COOP_DISC, starts) as s:
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
