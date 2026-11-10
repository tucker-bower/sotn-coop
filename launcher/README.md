# launcher

The app players run: menus, castles, both games on screen and bug reports.

| File | What it does |
|---|---|
| `app.py` | The player's app: first run, menus, lobby and starting games. |
| `archive.py` | Castles and their savestates. |
| `assets/` | Icons and the bundled test castles. |
| `bossrush.py` | Boss rush: loads the next boss when one falls. |
| `bossstarts.py` | Builds a start outside each boss, with a typical player's progress. |
| `characters.py` | Builds the Marias from the player's own discs: Co-op and Ultimate Maria from the DXC disc, Saturn Maria from the Saturn disc. |
| `debugstarts.py` | Builds savestates anywhere on the route, from the player's own disc. |
| `display.py` | The window: menus, games and their layout. |
| `gameview.py` | The frame loop: both games, pads, sound, joint saves and F9 reports. |
| `paths.py` | Where the player's files live. |
| `platform_android.py` | What the launcher needs from an Android device. |
| `report.py` | F9: writes the bug report zip and emails it. |
| `crashwatch.py` | Notices a game that has crashed or hung. |
| `crash_window.py` | The bug report window after a crash: its own process, and nothing is sent unless the player says so. |
| `sdlqueue.py` | Android's sound, pushed straight to SDL (SDL_QueueAudio). |
| `saturn_maria.py` | Makes Saturn Maria's art from the player's Saturn disc: a port of SOTN Ultimate's converter. |
| `saturn_richter.py` | Makes Ultimate Richter's coat from the player's Saturn disc and RIC.BIN: a port of SOTN Ultimate's converter. |
| `saturn_maria_sounds.py` | Makes Saturn Maria's two sound banks from the Saturn disc: a Saturn synth and the PS1 sample encoder, ported from SOTN Ultimate. |
| `test_android_disc.py` | Checks Android's disc setup. |
| `test_castles.py` | Checks castle names, joiners' copies and slot rules. |
| `test_characters.py` | Checks Maria's build from a DXC disc. |
| `test_report.py` | Checks what a report sends and removes. |
| `test_audio.py` | Checks that uneven frames cost one short gap, not a crackle. |
| `test_crash_window.py` | Checks what counts as stopped, and that closing the crash window sends nothing. |
| `rules.py` | A castle's rules: every rule, its default, and what the game gets. |
| `test_rules.py` | Checks the rules: defaults, per-castle storage, the joiner's copy, the button remap. |
| `test_settings.py` | Checks the app's settings, and that PvP and aggro are no longer among them. |
| `test_ship_lists.py` | The files the app reads are in both the installer's and the APK's lists. |
| `uxdriver.py` | Plays the real app like a person and photographs every screen. |
| `winmenu.py` | The native Windows menu bar. |
