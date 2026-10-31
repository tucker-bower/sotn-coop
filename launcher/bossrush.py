"""Boss rush (docs/design/boss-rush.md; Tucker, 2026-10-31): the 22 bosses in story order, each
from its test castle's start (launcher/assets/test-castles). When one falls, both players load
into the next. Launcher-side only: it loads with the joint save (JointSave.resume), so it works
solo, on the couch and online (the host drives; the joiner follows the host's loads)."""

import json
from pathlib import Path

from link.jointsave import save_room, write_session

BUNDLE = Path(__file__).resolve().parent / "assets" / "test-castles"
GAME_PLAY, GAME_ENDING = 2, 9   # g_GameState
RECORDS = 0x30                  # g_Settings.timeAttackRecords
EVENTS = {  # time attack events (include/game.h) the game records when each boss falls
    "Slogra & Gaibon": 6, "Doppleganger10": 2, "Hippogryph": 7, "Minotaur & Werewolf": 4, "Lesser Demon": 17,
    "Karasuman": 10, "Olrox": 1, "Succubus": 9, "Scylla": 5, "Cerberus": 13, "Granfaloon": 3,
    "The Creature": 16, "Darkwing Bat": 20, "Akmodan II": 19, "Medusa": 15, "Death": 12, "Doppleganger40": 18,
    "Fake Trevor, Grant & Sypha": 11, "Beelzebub": 8, "Galamoth": 21, "Dracula": 0}
ENDS_GAME = {"Richter", "Dracula"}  # no record: their death starts the ending (boss.c, D130 / D134)
WON_PAUSE = 180                 # frames between a win and the next load: the death sequence, a breath
RICHTER_PAUSE = 90              # his: the next load comes before his ending's fade (some 320 frames),
                                # whose state a load can't leave


def bosses(bundle=BUNDLE):
    """[{name, save (bytes), start}] in story order."""
    index = json.loads((bundle / "index.json").read_text())["castles"]
    rows = sorted((v["order"], k[len("Boss: "):], v) for k, v in index.items() if k.startswith("Boss: "))
    return [{"name": name, "save": (bundle / v["save"]).read_bytes(), "start": v["start"]} for _, name, v in rows]


def first_save(bundle=BUNDLE):
    b = bosses(bundle)[0]
    return b["save"], b["start"]


class BossRush:
    """Watches the fight and loads the next boss. state: the castle's info["rush"] (index, frames,
    splits, best, done), kept by the caller (on_change)."""

    def __init__(self, joint, games, state, on_change=None, bundle=BUNDLE):
        self.joint, self.games, self.state = joint, games, state
        self.on_change = on_change or (lambda: None)
        self.rows = bosses(bundle)
        self.state.setdefault("index", 0)
        self.state.setdefault("frames", 0)
        self.state.setdefault("splits", [])
        from module import symbols
        self._final_gone = symbols()["g_CoopRichterState"]
        self.won_at = None      # frame count when the current boss fell
        self.fight_frames = 0   # this boss's frames so far

    @property
    def boss(self):
        return self.rows[self.state["index"]]

    def _beaten(self):
        g = self.games[0]
        name = self.boss["name"]
        if name in ENDS_GAME:  # boss.c's g_CoopRichterState bit 0: the final boss died (either game)
            return any(x.read("g_GameState") == GAME_ENDING or x.read(self._final_gone) & 1 for x in self.games)
        return g.read("g_GameState") == GAME_PLAY and g.read("g_Settings", "<i", RECORDS + 4 * EVENTS[name]) != 0

    def tick(self):
        """Once per frame."""
        if self.state.get("done"):
            return
        if self.games[0].read("g_GameState") == GAME_PLAY:  # loads and the ending don't count
            self.state["frames"] += 1
            self.fight_frames += 1
        if self.won_at is None:
            if self._beaten():
                self.won_at = self.state["frames"]
                self.state["splits"].append([self.boss["name"], self.fight_frames])
                if self.state["index"] == len(self.rows) - 1:  # Dracula: his ending plays
                    self.state["done"] = True
                    best = self.state.get("best")
                    self.state["best"] = self.state["frames"] if best is None else min(best, self.state["frames"])
                self.on_change()
            return
        wait = RICHTER_PAUSE if self.boss["name"] == "Richter" else WON_PAUSE
        if self.state["frames"] - self.won_at >= wait:
            self.advance()

    def advance(self):
        self.state["index"] += 1
        self.won_at, self.fight_frames = None, 0
        self.load()
        self.on_change()

    def load(self):
        """Both players into the current boss's start (also the retry when both fall: the joint
        save's file is this boss's)."""
        b = self.boss
        write_session(self.joint.path, [b["save"], b["save"]])
        # Saved in the boss's own stage (the Succubus, Scylla, Dracula): the save's room is the
        # start; arriving again would reload it and replay its opening scene.
        same = save_room(b["save"])[0] == b["start"][0]
        self.joint.start = None if same else list(b["start"])
        self.joint.resume()

    def text(self):
        n, total = self.state["index"] + 1, len(self.rows)
        t = self.state["frames"] // 60
        clock = f"{t // 60}:{t % 60:02d}"
        if self.state.get("done"):
            return f"Boss rush done: {clock} (best {self.state['best'] // 3600}:{self.state['best'] // 60 % 60:02d})"
        return f"Boss rush {n}/{total}: {self.boss['name']}  ·  {clock}"
