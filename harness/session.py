"""Two-game sessions: two emulator processes, each with its own host, linked over localhost UDP.

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

def _worker(conn, disc, start, rank):
    from emu import Emu
    from link.adapter import HarnessAdapter
    from link.host import Host
    from link.mailbox import Mailbox
    from link.transport import UdpTransport
    from module import symbols

    try:
        with Emu(disc) as emu:
            if start:
                emu.load_state_file(savestate(disc, start))
            mailbox = Mailbox(HarnessAdapter(emu), symbols()["g_CoopLink"])
            transport = UdpTransport()  # any free port, so sessions can run in parallel
            host = Host(mailbox, transport, rank)
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
                elif cmd == "call":  # any Emu method or mailbox method
                    target, name, a, kw = args
                    obj = {"emu": emu, "mailbox": mailbox, "host": host}[target]
                    conn.send(("ok", getattr(obj, name)(*a, **kw)))
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
    """Proxy to one worker: any Emu method by name, plus link/mailbox helpers."""

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

    def mailbox(self, name, *a, **kw):
        return self._ask("call", ("mailbox", name, a, kw))

    def host(self, name, *a, **kw):
        return self._ask("call", ("host", name, a, kw))

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


class Session:
    def __init__(self, disc, starts=("entrance", "entrance"), session_file=None):
        """disc: one disc for both games, or (disc A, disc B). session_file: run the couch
        launcher's joint saves (link.jointsave) into that file, every frame."""
        self.disc, self.starts, self.session_file = disc, starts, session_file
        self.joint = None

    def __enter__(self):
        ctx = mp.get_context("spawn")
        self.games = []
        discs = self.disc if isinstance(self.disc, (tuple, list)) else (self.disc, self.disc)
        for i, start in enumerate(self.starts):
            parent, child = ctx.Pipe()
            proc = ctx.Process(target=_worker, daemon=True, args=(child, str(discs[i]), start, i))
            proc.start()
            self.games.append(Game("AB"[i], parent, proc))
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
