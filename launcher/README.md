# launcher

The app players run: menus, castles, both games on screen and bug reports.

| File | What it does |
|---|---|
| `app.py` | The player's app: first run, menus, lobby and starting games. |
| `archive.py` | Castles and their savestates. |
| `assets/` | Icons and the bundled test castles. |
| `bossrush.py` | Boss rush: loads the next boss when one falls. |
| `bossstarts.py` | Builds a start outside each boss, with a typical player's progress. |
| `characters.py` | Builds Maria from the player's own DXC disc. |
| `debugstarts.py` | Builds savestates anywhere on the route, from the player's own disc. |
| `display.py` | The window: menus, games and their layout. |
| `gameview.py` | The frame loop: both games, pads, sound, joint saves and F9 reports. |
| `paths.py` | Where the player's files live. |
| `platform_android.py` | What the launcher needs from an Android device. |
| `play.py` | **Vestigial.** Developer presets, started only by `scripts/install_launcher.sh`'s shortcuts. |
| `report.py` | F9: writes the bug report zip and emails it. |
| `crashwatch.py` | Notices a game that has crashed or hung. |
| `crash_window.py` | The bug report window after a crash: its own process, and nothing is sent unless the player says so. |
| `smoke.py` | **Vestigial.** Early end-to-end check, not in any runner; the UI flows in `uxdriver.py` replaced it. |
| `test_android_disc.py` | Checks Android's disc setup. |
| `test_castles.py` | Checks castle names, joiners' copies and slot rules. |
| `test_characters.py` | Checks Maria's build from a DXC disc. |
| `test_report.py` | Checks what a report sends and removes. |
| `test_audio.py` | Checks that uneven frames cost one short gap, not a crackle. |
| `test_crash_window.py` | Checks what counts as stopped, and that closing the crash window sends nothing. |
| `rules.py` | A castle's rules: every rule, its default, and what the game gets. |
| `test_rules.py` | Checks the rules: defaults, per-castle storage, the joiner's copy, the button remap. |
| `test_settings.py` | Checks the app's settings, and that PvP and aggro are no longer among them. |
| `uxdriver.py` | Plays the real app like a person and photographs every screen. |
| `winmenu.py` | The native Windows menu bar. |
