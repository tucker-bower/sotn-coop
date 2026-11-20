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
| `discs.py` | Which disc a file is (PlayStation, PSP or Saturn), by what's in it. |
| `display.py` | The window: menus, games and their layout. |
| `ui/` | The menus in the game's own style: the theme, the menu toolkit and one file per screen. |
| `discord_status.py` | Discord's "Playing SoTN Co-op": Rich Presence over the local Discord app's pipe (needs the app's Discord client id). |
| `test_discord_status.py` | Checks the Discord status against a fake Discord. |
| `streamer.py` | Streamer mode: hides room codes, connect codes and IP addresses from every text the app draws. |
| `test_streamer.py` | Checks what streamer mode hides, and that both menus' text goes through it. |
| `test_ui.py` | Checks the menus' font, lists and screens with a controller, the keyboard and the mouse, on made-up art. |
| `gameart.py` | Reads the game's own art for the menus from the player's disc: font, logo, portraits, save icons. |
| `gamesound.py` | Decodes the title music and menu sounds from the player's disc. |
| `gameview.py` | The frame loop: both games, pads, sound, joint saves and F9 reports. |
| `library.py` | The player's game discs: the co-op disc with mods, kept small, switched between. |
| `move.py` | Moves a player's things from Documents into the install's folder, once, whole or not at all. |
| `paths.py` | Where the player's files live. |
| `platform_android.py` | What the launcher needs from an Android device. |
| `report.py` | F9: writes the bug report zip and emails it. |
| `crashwatch.py` | Notices a game that has crashed or hung. |
| `crash_window.py` | The bug report window after a crash: its own process, and nothing is sent unless the player says so. |
| `sdlqueue.py` | Android's sound, pushed straight to SDL (SDL_QueueAudio). |
| `saturn_maria.py` | Makes Saturn Maria's art from the player's Saturn disc: a port of SOTN Ultimate's converter. |
| `saturn_richter.py` | Makes Ultimate Richter's coat from the player's Saturn disc and RIC.BIN: a port of SOTN Ultimate's converter. |
| `saturn_maria_sounds.py` | Makes Saturn Maria's two sound banks from the Saturn disc: a Saturn synth and the PS1 sample encoder, ported from SOTN Ultimate. |
| `sprites.py` | Reads each character standing from the player's discs, for the main menu's title. |
| `test_castles.py` | Checks castle names, joiners' copies and slot rules. |
| `test_library.py` | Checks game discs: names, removal, the old randomizer setting, the Alternate Scarlet Symphony download, images kept. |
| `test_one_folder.py` | Checks the one install folder: relative paths, the move from Documents, a disc copied in. |
| `test_disk_full.py` | Checks a full disk: no half-written save, card, savestate or disc copy left, and nothing crashes (#277). |
| `test_update.py` | Checks updates against a fake GitHub: found, downloaded, checked, refused, and installed on one press. |
| `test_link_errors.py` | Checks that a failure in the link never stops a player's game. |
| `test_report.py` | Checks what a report sends and removes. |
| `test_crash_window.py` | Checks what counts as stopped, and that closing the crash window sends nothing. |
| `randomizer_tool.py` | Rolls a randomized castle: the randomizer and Node.js, downloaded on first use. |
| `rules.py` | A castle's rules: every rule, its default, and what the game gets. |
| `test_rejoin.py` | Checks rejoining: a castle keeps its room code while recent, and Join offers the last room. |
| `test_rules.py` | Checks the rules: defaults, per-castle storage, the joiner's copy, the button remap. |
| `test_screens_fit.py` | Draws every screen with long content and fails on any text cut off. |
| `test_settings.py` | Checks the app's settings, and that PvP and aggro are no longer among them. |
| `test_ship_lists.py` | The files the app reads are in both the installer's and the APK's lists. |
| `update.py` | Updates from GitHub: finds a newer release, downloads and checks its installer, runs it. |
| `uxdriver.py` | Plays the real app like a person and photographs every screen. |
| `winmenu.py` | The native Windows menu bar. |
