"""M17 criterion 5 (design/M17-more-players.md): what four linked games cost. Manual: no runner
includes it. Prints each game's emulated frame (worker time), the hosts' link time per frame, and
what each game sends per second, for two, three and four games walking around one stage.

    python harness/m17_measure.py
"""
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from session import Session  # noqa: E402
from module import COOP_DISC  # noqa: E402


def measure(n, frames=600):
    with Session(COOP_DISC, starts=("nz0",) * n) as s:
        s.step(120)
        for g in s.games:
            g.host_ms()  # (drop the warm-up's)
        sent0 = [sum(st["sent"] for st in g._ask("call", ("hosts", "status", (), {}))) for g in s.games]
        t0 = time.perf_counter()
        pads = ("left", "right", "", "left")[:n]
        for i in range(frames):
            s.step(1, tuple(p if (i // 90) % 2 else ("right" if p == "left" else "left") for p in pads))
        wall = (time.perf_counter() - t0) / frames * 1000
        host = [statistics.mean(g._ask("host_ms")) for g in s.games]
        sent = [(sum(st["sent"] for st in g._ask("call", ("hosts", "status", (), {}))) - s0) / (frames / 60) / 1000
                for g, s0 in zip(s.games, sent0)]
        return wall, host, sent


def main():
    for n in (2, 3, 4):
        wall, host, sent = measure(n)
        print(f"{n} games: {wall:.1f} ms per frame for all {n} (stepped one after another: {wall / n:.1f} each); "
              f"link {max(host):.2f} ms per frame at most; sent {', '.join(f'{k:.0f}' for k in sent)} KB/s")


if __name__ == "__main__":
    main()
