# patcher

Turns the player's own disc into the co-op disc without shipping game data.

| File | What it does |
|---|---|
| `bps.py` | Makes and applies BPS patches. |
| `patcher.py` | The disc patcher, for players and for release builds. |
| `sectors.py` | CD sector checksums, so a patch never carries them. |
| `test_patcher.py` | Checks the patch rebuilds our disc byte for byte. |
