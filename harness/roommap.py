"""Rooms as the game's collision sees them, from the stage files sotn-decomp extracted from the
player's own disc (assets/st/<stage>: layers.json, tilemaps, tile collision; game data, never
committed). For tests that need a real place to stand in a room (session_crawl.py)."""

import json
import struct
from pathlib import Path

from coop_env import TOOLS

TILE = 16
ROOM_TILES = 16      # a room's screen is 16 by 16 tiles
BODY_TILES = 3       # a standing player needs this many free tiles above the floor
STAND_ABOVE = 25     # px from the floor's top to a standing player's y


def _assets(area):
    return TOOLS["out"].parent / "src" / "sotn-decomp" / "assets" / "st" / area


class Room:
    def __init__(self, room_id, layer, grid):
        self.room_id, self.grid = room_id, grid
        self.w, self.h = len(grid[0]) * TILE, len(grid) * TILE
        self.left, self.top = layer["left"], layer["top"]

    def solid(self, tx, ty):
        if not (0 <= ty < len(self.grid) and 0 <= tx < len(self.grid[0])):
            return True
        return self.grid[ty][tx] != 0

    def floors(self):
        """(x, y) where a player stands: free tiles for a body, something under its feet."""
        out = []
        for ty in range(BODY_TILES, len(self.grid)):
            for tx in range(1, len(self.grid[0]) - 1):
                if self.solid(tx, ty) and not any(self.solid(tx, ty - k) for k in range(1, BODY_TILES + 1)):
                    out.append((tx * TILE + TILE // 2, ty * TILE - STAND_ABOVE))
        return out

    def spot_near(self, x, y):
        if not any(any(row) for row in self.grid):  # no collision known: the point asked for
            return (x, y)
        f = self.floors()
        return min(f, key=lambda p: (p[0] - x) ** 2 + (p[1] - y) ** 2) if f else None


def rooms(area):
    """The stage's rooms that are places (not loading rooms), each with its collision grid."""
    base = _assets(area)
    if not (base / "layers.json").exists():  # not extracted (NO1): rooms with no collision, the middle as the spot
        out = []
        for i, r in enumerate(json.loads((base / "rooms.json").read_text())):
            if r["tileDefId"] != -1:
                w, h = (r["right"] - r["left"] + 1) * ROOM_TILES, (r["bottom"] - r["top"] + 1) * ROOM_TILES
                out.append(Room(i * 8, r, [[0] * w for _ in range(h)]))
        return out
    layers = json.loads((base / "layers.json").read_text())
    cols = {}
    out = []
    for i, r in enumerate(json.loads((base / "rooms.json").read_text())):
        if r["tileDefId"] == -1:
            continue
        layer = layers[r["layerId"]]["fg"]
        if not layer or layer.get("isLoadingRoom"):
            continue
        tdef = layer["tiledef"]
        if tdef not in cols:
            cols[tdef] = (base / json.loads((base / tdef).read_text())["collisions"]).read_bytes()
        w = (layer["right"] - layer["left"] + 1) * ROOM_TILES
        h = (layer["bottom"] - layer["top"] + 1) * ROOM_TILES
        raw = (base / layer["data"]).read_bytes()
        tiles = struct.unpack(f"<{len(raw) // 2}H", raw)
        col = cols[tdef]
        grid = [[col[tiles[y * w + x]] if tiles[y * w + x] < len(col) else 0 for x in range(w)] for y in range(h)]
        out.append(Room(i * 8, layer, grid))
    return out
