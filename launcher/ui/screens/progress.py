"""A long job, in the game's style: what's happening, and a bar that fills (the game's own
gold on its window blue). The job runs in a thread; this returns its result or raises its error."""

import threading

import pygame

from ..theme import DIM, GOLD, wrap

BOX = (60, 80, 360, 100)


def progress(m, heading, about, task):
    state = {"done": 0, "total": 0, "result": None, "error": None, "finished": False}

    def report(done, total):
        state["done"], state["total"] = done, total

    def work():
        try:
            state["result"] = task(report)
        except BaseException as e:  # noqa: BLE001 - given to the caller
            state["error"] = e
        state["finished"] = True

    threading.Thread(target=work, daemon=True).start()
    t, s = m.theme, m.s
    while not state["finished"]:
        m.poll(quiet=("up", "down", "left", "right", "ok", "back"))
        m.begin(heading, about)
        m.window(BOX)
        x = BOX[0] + 12
        t.text(s, heading[:42], x, BOX[1] + 10, GOLD)
        for k, line in enumerate(wrap(about, 42)[:2]):
            t.text(s, line, x, BOX[1] + 26 + k * 10, DIM)
        bar = pygame.Rect(x, BOX[1] + 62, BOX[2] - 24, 10)
        pygame.draw.rect(s, (0, 0, 16), bar)
        if state["total"]:
            fill = bar.w * min(1.0, state["done"] / state["total"])
        else:  # no measure: a block that sweeps across
            fill = 0
            w = bar.w // 5
            at = (pygame.time.get_ticks() // 8) % (bar.w + w) - w
            pygame.draw.rect(s, GOLD, pygame.Rect(bar.x + max(0, at), bar.y, max(0, min(w, bar.right - bar.x - at, w + at)), bar.h))
        pygame.draw.rect(s, GOLD, (bar.x, bar.y, int(fill), bar.h))
        pygame.draw.rect(s, (255, 255, 255), bar, 1)
        if state["total"]:
            t.text_right(s, f"{int(100 * min(1.0, state['done'] / state['total']))}%", BOX[0] + BOX[2] - 12, BOX[1] + 80, DIM)
        m.footer("Please wait", "Please wait")
        m.show()
    if state["error"]:
        raise state["error"]
    return state["result"]
