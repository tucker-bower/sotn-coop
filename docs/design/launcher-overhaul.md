# Launcher overhaul: design and build plan

Approved by Tucker, 2026-11-10. Issue 227. Closes issues 82 and 213, and part of 144.

## Context

The launcher works but looks like a debug tool: Georgia text on a gradient, text-only lists, and a flow that grew a screen at a time. Three things are missing or awkward for players:

- There is no update check (issue 82). Players find new versions by hand.
- Discs are added through Settings › Game files, one file dialog at a time. The Saturn disc is hard enough to find that a player reported it missing (issue 213).
- The order of screens differs between solo, couch and online, the castle rules are a flat list of 24 text rows, and character select shows names only.

The outcome: one flow for every mode, styled as the game's own menu (mock-up A, chosen 2026-11-10), with the game's font and visuals taken from the player's own disc wherever possible, and all of it usable with a controller, keyboard or mouse.

## Decisions already made (Tucker, 2026-11-10)

| Question | Decision |
|---|---|
| Style | A: the game's own menu. Navy windows, thin double borders, the game's font and hand cursor. Use the game's fonts and visuals throughout. |
| Updating | Download and install in the launcher, one click. |
| App settings | Stay in the Windows menu bar. A controller-reachable Options screen mirrors it for fullscreen, controllers and Android. |
| Castle option defaults | Every balancing option on. PvP, Hang onto the bat and Button remap stay off. |
| Mods | They live with the discs: the main menu item is **Discs & mods**. A player keeps several game discs (vanilla co-op, a randomizer seed, a seed with hacks) and switches between them. |
| SOTN Editor's hacks | A checklist in the launcher of the hacks we've tested. We ship each as a small patch. |
| Untested mods | A `.ppf` or modded disc we haven't tested is allowed when it layers cleanly, and is marked "Untested with co-op". |
| Difficulty | A preset at the top of the castle options: Easy, Medium (default), Hard, Nightmare, setting enemy HP, damage taken and XP. No Damage dealt slider. |
| One folder | The installer asks where and makes `sotn-coop` there. The program, discs, castles, savestates and everything else live in it. |
| Links | GitHub and Discord on the main menu, mouse only. Every mod and author credited in the README. |

## The flow

```
launch
 └─ Update available?  ── Update now / Later            (only when a newer release exists)
 └─ PS1 disc attached? ── no → Discs screen (can't leave without it, except Quit)
 └─ Main menu:  Solo · Couch co-op · Online co-op · Discs & mods · Options · Quit
      Solo / Couch ──────────────┐
      Online → pop-up: Host / Join
         Host ───────────────────┤
         Join → room code ───────┼──────────────────────────→ Character select → game
                                 ▼
                    Castle screen: Continue · New castle · Load castle
                       Continue ──────────────────────────→ Character select → game
                       New castle → name → Castle settings → Character select → game
                       Load castle → castle list ─────────→ Character select → game
```

A joiner never sees the castle screen or castle settings, for a new or a continued castle. The host's room code is on the character select screen.

### 1. Update prompt
- At launch a background thread asks GitHub for the latest release (`api.github.com/repos/tucker-bower/sotn-coop/releases/latest`, 3 s timeout). It never delays the menu: no answer means no prompt. The request carries only `sotn-coop/<version>` as its user agent.
- A newer version shows one window: "Version 0.18.0 is available (you have 0.17.0)", the release's player changelog, and "Your castles, saves and discs are safe: they're in the data folder, and the update only replaces the program." Buttons: **Update now**, **Later**.
- **Windows:** downloads `SOTN-Coop-setup.exe` with a progress bar, checks it against the release's `SHA256SUMS.txt`, runs it silently, quits; the installer restarts the launcher. A failed download or a bad checksum says so and goes on to the menu.
- **Android:** downloads `SOTN-Coop.apk`, checks it, and hands it to the system installer (the player confirms there). If the install permission is refused, it opens the release page.
- Later: the main menu's footer keeps "Update available", and Help › Check for updates opens the prompt again. A dev checkout (no installer) never checks.

### 2. Discs screen
- Three slots side by side, each a window:
  - **Symphony of the Night · PlayStation (USA)** — "Required".
  - **Dracula X Chronicles · PSP (USA)** — "Optional: unlocks Co-op Maria and Ultimate Maria".
  - **Symphony of the Night · Sega Saturn (Japan)** — "Optional: unlocks Saturn Maria and Ultimate Richter".
- Drop a file anywhere on the window, or select a slot to browse. A dropped file is identified by its contents, not by which slot it landed on, so several files can be dropped at once.
- Each slot shows its state: empty, working (progress), ready (file name, a tick, and the characters it unlocked, with their portraits), or refused in plain words ("That's the European version: co-op needs the USA disc").
- **Continue** is disabled until the PlayStation slot is ready. On first run the only other way out is Quit. Reached later from the main menu's Discs & mods item, it has Back.
- Before the PlayStation disc is attached there is no game art to draw with, so this screen and the update prompt use the same layout drawn plainly (flat navy windows, a system font). Once the disc is in, the screen redraws in the game's font.
- SDL gives no "file is hovering" event, so the window can't highlight while a file is dragged over it. The slots carry a standing "Drop your disc here, or select to browse" line instead.
- Android has no drag and drop: the slots open its own file picker, as now.
- The BIOS is not a disc a new player needs: it moves to the menu bar (Options › BIOS…).
- On first run this is all the screen shows. Reached later from the main menu as **Discs & mods**, it has a second part below the three slots: the game discs.

### 2b. Game discs and mods (the lower half of Discs & mods)

A **game disc** is what a castle is played on: the player's PlayStation disc, plus co-op, plus any mods. The launcher keeps a list of them and one is in use at a time.

```
 Game discs
 ☞ Co-op (no mods)                                   in use
   Randomizer · seed abc · casual                    3 castles
   Randomizer · seed xyz · safe  + Fast warp, Minimap
   Alternate Scarlet Symphony                        untested with co-op
   New game disc…
```

- **Co-op (no mods)** always exists and can't be removed.
- **New game disc…** opens a builder with four parts, any of which can be left empty:
  1. **Randomizer**: drop or browse for a randomized disc (`.cue`) or a seed's `.ppf` from sotn.io. Its seed and preset are read from it, as now.
  2. **Hacks**: a checklist of the SOTN Editor hacks we've tested, each with a one-line description (Fast warp, Minimap, Quick items…). Only tested ones are listed.
  3. **Alternate Scarlet Symphony -Final-**: one switch. The launcher downloads its `.ppf` (5 MB) from SOTN Editor's own GitHub release, at the version we tested, checks it against a checksum we ship, and keeps it. We don't put the patch in our installer: it's a full remix of the game, so it comes from its author, and the author's release counts the download. With no internet the switch says so, and a `.ppf` the player already has can be dropped instead.
  4. **Another patch**: drop or browse for any other `.ppf` (a hack we haven't tested).
  Then **Make disc**: about a minute, with progress. It's named from what's in it, and the player can rename it.
- **What we've tested** (every one layered, booted and passed its test, per `harness/mods.py`'s records): 68 of the randomizer's 72 presets (the other four its own command line can't make), the randomizer's code-patching extras together (turkey mode, colour rando, magic max, antifreeze, my purse, IWS, fast warp, no prologue, item names), the 28 SOTN Editor hacks alone and all at once, and Alternate Scarlet Symphony -Final-. Nothing else has been tested. The randomizer's extras arrive inside the randomized disc, so they need no entry of their own. ASS -Final- is shown as tested, whether downloaded by the switch or dropped (recognised by its checksum). Its 34 own hacks aren't tested yet (issue 181) and aren't offered. SOTN Ultimate is the upstream of our Ultimate and Saturn characters, so it's already in as characters and needs no entry as a disc mod.
- **Credits on the screen.** Each mod's row names its author, and the builder has a "About these mods" line that opens their pages.
- Each row says what it is in plain words and how it stands with co-op: nothing for tested, "each part tested alone" for a combination, "untested with co-op" for an unknown patch. A mod that changes the same code as co-op is refused when the disc is made, saying which mod, as the randomizer's are today.
- OK on a row puts it in use. Square / X: rename, remake, or remove (asks first when castles are on it).
- **Castles remember their disc.** A new castle is made on the disc in use, and the castle screen says which ("New castle · on Randomizer seed abc"). Continue and Load castle switch to the castle's own disc by themselves; today's "this castle is on another disc, play anyway?" question goes away. The castle list shows each castle's disc.
- **Online:** the host's disc travels in the handshake, as its seed does today. A joiner on a different disc is told which disc the host is on. If the joiner has it, one press switches and reconnects with the same room code; if not, the message says what to make ("Randomizer seed abc, casual, with Fast warp"). Sending the host's mods to the joiner automatically is not in this design.
- **Storage.** Each game disc is kept as a recipe (what's in it) and its mods as small patches against the player's own disc, in the data folder's `discs/`: kilobytes, not a 540 MB image each. A randomized `.cue` is turned into such a patch when it's added, so the player can delete the file sotn.io gave them. The playable image is built when a disc is put in use; the three most recently used images are kept and older ones are rebuilt on demand (about a minute). The audio track is never copied: every image's `.cue` points at the player's own.
- After a launcher update, the disc in use is remade for the new co-op patch at launch (as now), and the others when they're next used.

### 3. Main menu
Mock-up A: a title window, the menu on the left with the hand cursor, and on the right a window about the selected item (for Solo and Couch, the last castle: name, area, level, and its player's portrait). Footer: version, discs attached, "Update available" when there is one, and the controls for the device last used.

Items: Solo, Couch co-op (not on Android), Online co-op, Discs & mods, Options, Quit. The footer names the game disc in use when it isn't the plain co-op one.

Two links sit in a corner of the main menu, for the mouse (or a tap on Android) only; a controller and the keyboard never land on them:
- **GitHub** → `https://github.com/tucker-bower/sotn-coop`
- **Join our Discord and meet people to play with!** → `https://discord.gg/q7V9eFtAW`

Each opens in the system's browser. They underline on hover and aren't part of the focus order.

Online co-op opens a small pop-up over the menu: **Host** / **Join**. Join asks for the room code (as now: typed, pasted, or Square / X to paste), then goes straight to character select.

### 4. Castle screen
- **Continue** is first and selected, and names what it loads: "Continue · Tucker, Clock Tower, Lv 31". It's the most recently played castle. With no castles yet it's absent and New castle is selected.
- **New castle** → name it (or leave empty, as now) → castle settings → character select.
- **Load castle** → a scrolling list of every castle, most recent first, each with its area, level, last played and "rules changed" when they differ from the defaults. Square / X / right-click on a castle opens its settings. Test castles stay at the bottom of this list; a boss rush is a new castle's mode (castle settings).

### 5. Castle settings
- **Mode** is the first row on a new castle: **Story** (the game from its start) or **Boss rush** (all 22 bosses back to back, each with a typical player's progress, timed; `design/boss-rush.md`). It's chosen once: an existing castle shows its mode and can't change it. Boss rush leaves the bottom of the Load castle list (Tucker, 2026-11-10: it belongs in the castle settings); the test castles stay there.
- **Difficulty** is the next row: Easy, Medium, Hard, Nightmare. Left / right changes it, and the sliders it sets move at once:

  | Difficulty | Enemy HP, with a partner | Enemy HP, alone | Damage taken | XP gain |
  |---|---|---|---|---|
  | Easy | 100% | 50% | 50% | 150% |
  | **Medium** (a new castle's) | 200% | 100% | 100% | 100% |
  | Hard | 300% | 150% | 150% | 50% |
  | Nightmare | 400% | 200% | 200% | 50% |

  Alone, enemy HP is half the co-op figure, so Medium alone is the original game. Moving any of those four sliders by hand shows the difficulty as **Custom**. The difficulty isn't stored: it's whichever row the four values match, so today's castles, which are all at 200 / 100 / 100 / 100, read as Medium with no migration.
- The **Damage dealt** slider is removed (Tucker, 2026-11-10: players shouldn't feel nerfed; enemy HP does the same job). A castle that had changed it goes back to 100%. The game's `dealtPct` word stays in the mailbox, always 0, so this needs no module change; removing the word is added to issue 224's list.
- One screen, grouped under headings instead of 24 flat rows: **Balance** (difficulty and the five sliders), **Sharing** (level, purse), **Falling and reviving**, **Staying together** (boss and scene pulls, map teleport), **Richter and Maria** (growth, stats, relic moves, jumps, off-hand, familiars, gear), **Extras** (bat carry, PvP, button remap).
- Sliders are bars with their value; toggles are switches. Left / right or a drag moves a slider; OK or a click flips a toggle. The selected row's explanation shows in a window at the bottom.
- A row that differs from its default is marked, and **Back to the defaults** restores them all.
- Every other default is unchanged from `launcher/rules.py` today: all balance options on.
- Reached from New castle (with a **Start** button), from the castle list, and from the pause menu in a game. A joiner sees the host's, read-only, from the pause menu only.

### 6. Character select
- One window per local player (one for solo and online, two for couch), plus the partner's window online.
- A player joins by pressing a button on their controller or Enter, as now. Left / right changes character.
- An available character shows its portrait, large, and its name, with the one-line note it has today ("Alucard's gear and relics").
- An unavailable one shows an empty frame and "Co-op Maria — attach your Dracula X Chronicles disc (PSP) to unlock". OK on it opens the Discs screen and comes back.
- Host: the partner's window shows the room code, large, "copied to your clipboard", and the connection's progress; once connected, the ping. Joiner: the room they're joining and the same progress.
- Each player's shortcuts toggle stays here (Triangle / Y).
- The game starts when every local player is ready and, online, the partner is connected.

### 7. Options
- The Windows menu bar stays, with what it has now plus what leaves the old Settings screen: View (layout, fullscreen), Options (music, menu music and volume, partner's sounds, partner's health bar, tint, spells on triggers, Alucard's health bar, show ping, controls, BIOS), Help (how to play, online troubleshooting, check for updates, about, developer).
- The main menu's **Options** item opens a screen built from the same table, so a controller, fullscreen and Android reach every item. One table (`MENUS`) feeds both, so they can't drift apart.

## One folder for everything

Today the program is in `%LOCALAPPDATA%\Programs\SOTN Co-op`, the player's castles, settings and reports are in `Documents\SOTN Co-op`, and the co-op disc is made next to wherever the player's own disc image is. Tucker, 2026-11-10: all of it goes in one folder the player chooses.

```
<where the player chose>\sotn-coop\
    SOTN Co-op.lnk            starts the launcher
    app\  python\             the program (replaced by an update)
    data\                     everything the player has (never touched by an update or an uninstall)
        settings.json
        castles\              castles, their memory cards and savestates
        discs\                the player's PlayStation disc (a copy), every game disc and mod patch
        characters\           Maria, Saturn Maria, Ultimate Richter
        art\                  the game's art and sounds, read from the disc
        reports\  logs
```

- **The installer asks where.** A folder page, prefilled with `C:\Games`, and it makes `sotn-coop` there. It still needs no admin rights, so it only installs where the player can write, which is also what lets the data live there.
- **`paths.data_dir()`** becomes `<install folder>\data` when the launcher runs from an install. `COOP_DATA` still overrides it (tests), a dev checkout keeps using `Documents\SOTN Co-op`, and Android keeps the app's own storage.
- **The player's PlayStation disc is copied in** when it's attached (540 MB), as Android does already. Every update and every game disc is made from it, so the folder then depends on nothing outside it, and the player can move or delete their original. The PSP and Saturn discs are only read once to make their characters, so they're not copied (up to 2 GB); if a later version needs them again and they've moved, the Discs screen asks.
- **Updates** replace `app\` and `python\` and nothing else.
- **Uninstalling** removes the program and asks "Also delete your castles, saves and discs?", with No selected.
- **Players who already have it.** The updater installs over the folder they have. On the first launch after, the launcher moves `Documents\SOTN Co-op` into `data\`, with progress, fixes the paths in settings, makes the co-op disc inside `data\discs`, and leaves a note in the old folder saying where everything went. If the move fails part-way (disk full) it keeps using the old place and says so; nothing is deleted until the copy is checked. To have the folder somewhere else, they move the whole `sotn-coop` folder and run the installer on it.
- Moving the folder to another PC or drive carries everything with it, since settings keep paths relative to the folder.

## Game art, from the player's disc

Nothing ripped from a disc is ever in the repo, the installer or the APK. `launcher/art.py` reads it from the player's PlayStation disc when the disc is attached and keeps PNGs in the data folder's `art/`, remade when the launcher's version changes.

| Art | Used for | Source |
|---|---|---|
| The menu font | All text | The game's font sheet |
| Menu window frame and hand cursor | Every window, the selection | The game's menu graphics |
| Richter's and Maria's portraits (48×72) | Character select, last castle | Already read by `link/portraits.py` (`ST0.BIN`, `DAI.BIN`) |
| Alucard's portrait | Same | His pause-menu or dialogue portrait |
| Saturn Maria, Ultimate Richter | Same | The Saturn disc's own portraits if they can be read; otherwise the PlayStation one, tinted as the partner tint does |
| Title logo | The title window | The title screen's graphics |
| The file select's animated save icons | Each castle, on Continue and in the castle list | The file select's own sprites (`SEL.BIN`), chosen by the save's `cardIcon`, which is in the castle's memory card |
| Title and file-select music | Plays in the menus | The disc's audio for that screen |
| Menu sounds (move, confirm, back) | Every screen | The game's sound samples |

**Castle icons.** In the game's file select every save has an animated icon, picked by where it was saved (`save->info.cardIcon`, `src/st/sel`). Each castle already holds that save in its memory card, so the launcher reads the icon number from the castle's own card and plays the file select's animation for it: on the Continue button, beside every row of the castle list, and in the main menu's "last castle" window. The selected castle's icon animates; the others hold their first frame, as the game does. A new castle with no save yet shows the game's "new game" icon. If the big sprites can't be found on the disc, the fallback is the 16×16 animated icon stored in the memory card itself, enlarged.

**Music and sounds.** The title screen's music loops in the menus and stops when a game starts or the launcher loses focus; move, confirm and back play the game's own menu sounds. They're decoded from the disc once, in the background after the disc is attached, and kept as audio files in the data folder beside the art. Until that's done, and on the first-run Discs screen, the menus are silent. Options gets **Menu music** (on / off) and **Menu volume**; both default on. In couch play each player's presses make the sounds; online nothing is sent.

Pixel art is enlarged by whole numbers only, so it stays crisp. Today the menus are drawn at 1032×532 and smoothed up to the window, which blurs them when maximized; the new screens draw at the window's real size, laid out in whole multiples of the game's pixel.

The font's and window graphics' exact places on the disc aren't in `docs/research.md` yet. Step 1 of the build is a spike that finds them from sotn-decomp's asset tables and records them there. If a piece can't be read from a given disc, that piece falls back to the plain drawing and the launcher still works.

The game's font has no lowercase accents or some symbols; text it can't draw falls back to the system font for that string (castle names typed by players).

## Code structure

`launcher/app.py` is 1,899 lines holding drawing, input, every screen and session start-up (issue 222). The overhaul moves the screens out and leaves session logic where it is:

| File | Holds |
|---|---|
| `launcher/ui/theme.py` | Colours, sizes, the window frame, text in the game's font with the plain fallback |
| `launcher/ui/widgets.py` | Window, list, button, slider, switch, pop-up, progress; one focus model for controller, keys and mouse |
| `launcher/ui/screens/` | One file per screen: `update.py`, `discs.py`, `home.py`, `castles.py`, `castle_settings.py`, `character_select.py`, `options.py`, `text_entry.py` |
| `launcher/art.py` | Rips and caches the game's art |
| `launcher/update.py` | Release check, download, checksum, starting the installer |
| `launcher/discs.py` | Identifies a dropped file (PS1, PSP, Saturn, or why not) and builds what it unlocks; today's `wizard`, `add_dxc`, `add_saturn` |
| `launcher/library.py` | The game discs: recipes, which is in use, building and pruning images, a castle's disc |
| `patcher/modded.py` | Makes a game disc from the retail disc, the co-op disc and a list of patches. Today's `randomizer.make`, taking several mods instead of one (`layer.merge` folded over each, conflicts named per mod) |
| `patcher/mods/` | One small patch and a description per tested SOTN Editor hack, with `index.json` (name, description, what tested it). Generated by `harness/mods.py` from the pinned editor, only for hacks whose `build.json` says tested; credited in `LICENSES/` (GPL-3.0, compatible with our AGPL-3.0) |
| `launcher/app.py` | The flow between screens and starting sessions; about half its size |

Reused as they are: `patcher.apply` and `DiscError` (disc checks), `characters.maria_blob` / `saturn_maria_blob` / `ultimate_richter_blob`, `link/portraits.py`'s disc reader, `rules.py` (gains a group per rule), `archive.Castle` (`all`, `summary`, `set_rules`), `rendezvous.make_room_code` / `find_connect_code`, `UI.wait_for`'s threading, `Launcher.partner_line`, `pick_file`, and `winmenu.MENUS` as the single table of options. The screens keep today's blocking style (`choice = screen(...)`), so `Navigate`, the pause menu and `gameview` need no change beyond the new look.

Also reused for mods: `patcher/layer.py` (`merge`, `relocate`, `adapt`), `patcher/ppf.py`, `randomizer.seed_info` / `describe`, the HELO `mod` and patch CRC check in `link/host.py`, and `castle.info["mod"]`, which becomes the castle's disc. The settings' single `randomizer` entry is migrated to a game disc on first launch, and castles made on it keep pointing at it.

Deleted: `UI.items`/`menu`/`frame`/`bar` in their current form, `settings_menu`, `game_files`, `randomizer_menu`, `castle_on_disc`'s question, `rules_menu`, `lobby`/`_card`/`_partner_card`, `online_menu`, `wizard` (each replaced by a screen).

## Build order (each step ends with its tests passing and a commit)

1. **Spike: the game's art and sound.** Find and rip the font, window frame, cursor, logo, portraits and the file select's save icons; find how the title music and menu sounds are stored and decode them. Record all of it in `docs/research.md`. Screenshot of a test window drawn with them, and the decoded audio played back.
2. **Theme and widgets**, with the plain fallback. Unit tests for focus movement and hit-testing.
3. **Main menu and castle screen** in the new style, wired to the existing session code. Tucker sees a screenshot here before the rest is restyled.
4. **Discs screen**, drag and drop, content identification. Closes issue 213.
5. **Character select** with portraits and the room code; online host and join flows.
6. **Castle settings** with groups, sliders and switches.
7. **Options screen** mirroring the menu bar; old Settings removed.
8. **Game discs.** `patcher/modded.py` and `launcher/library.py`: several discs, switching, castles on their own disc, the joiner's switch, migration of today's randomizer setting. The randomizer and "another patch" parts of the builder.
9. **Hacks checklist.** `harness/mods.py` writes `patcher/mods/` for the tested hacks; the builder's checklist applies them. Each shipped hack's disc is byte-identical to the one `mods.py` builds with the editor's own code.
10. **One folder.** The installer's folder page, `data\` inside the install, the PlayStation disc copied in, relative paths in settings, the move from Documents, the uninstaller's question. Done before updates, so the first self-update already lands in the new layout.
11. **Updates.** Closes issue 82. Proven against a local fake release server, then once against a real draft release.
12. **Android pass**: touch targets, no drag and drop, APK update.
13. Docs (`TECHNICAL_SUMMARY.md`, READMEs, `DECISION_LOG.md`, `M20-randomizer.md`, player help text), the gate, PR.

**Credits (in the mods PR).** The root `README.md`'s "Credits and thanks" gains a "Mods you can play with co-op" list, each with its author and a link to its GitHub page: the [randomizer](https://github.com/sotnrando/sotnrando) (the sotnrando team), [SOTN Editor](https://github.com/pddmergilla/sotn-editor) and Alternate Scarlet Symphony -Final- (pddmergilla), and [SOTN Ultimate](https://github.com/renanbianchi/sotn-ultimate) (renanbianchi, already credited for the characters). Author names are checked against each project's own page before they're written. `NOTICE` and `licenses/` gain SOTN Editor's GPL-3.0 for the hack patches we ship. The README also gets the Discord link.

Four PRs: steps 1–3, so the style is agreed on real screens before the rest is built; 4–7; 8–9 (mods, part of issue 144); 10–12.

## Acceptance criteria

1. With a newer release published, the launcher shows the update prompt within 5 s of launch, with the "saves are safe" line; with GitHub unreachable it reaches the menu no slower than today. *(test: `launcher_update`, fake server)*
2. Update now installs the new version and restarts into it, and every castle, setting and attached disc is as it was. A corrupted download is refused. *(test: checksum cases in `launcher_update`; one manual run against a draft release, with before/after listings of the data folder)*
3. With no PlayStation disc, the Discs screen is the first screen and nothing but Quit leaves it. *(test: `ui_startup`)*
4. A disc dropped on the window lands in the right slot whichever slot it was dropped on; a wrong disc is refused in plain words; PSP and Saturn discs unlock their characters. *(tests: `launcher_discs`, `ui_characters`)*
5. Solo, couch, host and join each follow the flow above; Continue loads the most recently played castle; a joiner never sees the castle screen. *(tests: `ui_solo`, `ui_couch`, `ui_online`)*
6. Character select shows a portrait and name for each available character, and the unlock line with no portrait for the others; the host's room code is on it. *(tests: `ui_characters`, `ui_online`, with screenshots)*
7. Every castle option is on the castle settings screen as a slider or switch, defaults as in `rules.py`, and a change reaches the game. *(tests: `launcher_rules`, `ui_rules`)*
8. Every screen can be completed with only a controller, only the keyboard, and only the mouse. *(test: `ui_inputs` runs the solo flow three times, once per device)*
9. Every item in the menu bar is in the Options screen. *(test: `launcher_settings` compares the two against `MENUS`)*
10. No ripped art is in the repo, the installer's file list or the APK's. *(test: `launcher_ship_lists`)*
11. Text and pixel art are crisp at 1280×720, maximized at 1920×1080 and in fullscreen. *(screenshots from `ui_window`)*
12. A player can make a plain co-op disc, two randomizer seeds and a seed with hacks, switch between them, and play a castle on each; each castle opens on its own disc without being asked. *(tests: `launcher_library`, `ui_randomizer`)*
13. Every hack in the checklist makes the same disc, byte for byte, as `harness/mods.py` makes with the editor's own code, and each has a passing `mod_editor_*` test. *(test: `mods_shipped_hacks`)*
14. An unknown `.ppf` that layers cleanly makes a disc marked untested; one that overlaps co-op is refused, naming the mod, and nothing is left half-made. *(test: `launcher_library`)*
15. A joiner on another disc is told the host's, and switches to it in one press when they have it. *(test: `ui_online` with a randomized host)*
16. Ten game discs take under 2 GB in the data folder (three images kept), and no audio track is copied. *(test: `launcher_library` measures the folder)*
17. Every castle shows its save's animated icon on Continue and in the castle list, the same icon the game's file select shows for that save. *(test: `launcher_castles` checks the icon number against the card; screenshots from `ui_solo`)*
18. The title music plays in the menus and stops when a game starts; move, confirm and back each play the game's sound; Menu music off silences the music. No decoded audio is in the repo, the installer or the APK. *(tests: `launcher_audio` on what the mixer is given, `launcher_ship_lists`)*
19. The Alternate Scarlet Symphony switch downloads the pinned `.ppf`, refuses one whose checksum differs, and makes a disc that passes `mod_ass_final`; with no internet it says so and the launcher goes on. *(test: `launcher_library`, fake server)*
20. The main menu's GitHub and Discord links open the right pages on a click, and no sequence of controller or keyboard presses selects them. *(test: `ui_inputs`)*
21. The README credits every supported mod with its author and a working link. *(test: `launcher_ship_lists` checks each mod in `patcher/mods/index.json` and the builder has a README entry)*
22. Difficulty is the first castle option; each of Easy, Medium, Hard and Nightmare sets the four sliders to the table's values at once, a new castle is on Medium, moving one of the four by hand shows Custom, and there is no Damage dealt slider. The game gets the values. *(tests: `launcher_rules`, `ui_rules`, `rules_enemy_hp`)*
23. After a fresh install to a chosen folder and an hour's use (a castle, a randomized disc, Maria added, a bug report), nothing of ours is outside that folder except the shortcuts: nothing in Documents, nothing next to the player's disc image. *(test: `launcher_one_folder` runs the flows with a watched home folder; one manual install on Windows)*
24. A player with castles in `Documents\SOTN Co-op` updates, and every castle, setting, disc and character is there and plays; an update and an uninstall (answering No) both leave `data\` byte for byte as it was; the folder moved to another drive still plays. *(tests: `launcher_one_folder`, `launcher_update`)*

## Verification

- While building: the tests named above, by name. When a step is done: `harness/run.py -c launcher`. Before each PR: the gate.
- The launcher is Python only, so the game tests run in a test worktree linked to `sotn-coop-fix`'s environment, as for the audit.
- Screenshots of every screen from `uxdriver.py` go in each PR. They show game art, so they stay in `.env/out/ux/`, never in git; the PR gets the ones of our own screens only where no ripped art is visible, and the rest are shown to Tucker locally.
- Real-device checks at the end: the Windows installer update, and the APK on the Android device in `LOCAL.md`.

## Risks

- **Finding the art.** If the font or frame can't be read reliably from the disc, the fallback drawing stays for that piece. The spike is first so this is known before anything is built on it.
- **Music format.** I haven't yet confirmed how the title music is stored on the disc. If it's a streamed track, decoding it in Python takes some seconds once, in the background; if it's sequenced (notes played by the console's sound chip), reproducing it faithfully is a much bigger job, and the fallback is to record it once from a hidden game booted to the title screen. The spike settles which.
- **Moving players' saves.** The move from Documents is the one step here that touches what players already have. It copies, checks, and only then removes; a failure leaves the old folder in use. It gets its own test with a full disk and an interrupted copy.
- **A folder the player can't write to.** With no admin rights the installer can't install there, so the folder page refuses it; `C:\Games` can be made by a standard user on a default Windows setup, and the page lets them pick another.
- **Disc space in the folder.** The copied disc (540 MB) plus up to three game disc images puts the folder at 2–3 GB. The Discs & mods screen shows the folder's size.
- **Silent install.** Windows may show a SmartScreen prompt for an unsigned installer started by the launcher (issue 83, code signing, would remove it). If it does, the prompt's text says to expect it.
- **Android install permission** differs by device; the fallback is the release page.
- **GitHub's limit** is 60 anonymous requests an hour per address: one check per launch, cached for an hour.
- **The UI tests** (`uxdriver.py`, 1,068 lines) drive today's screens by key presses and need rewriting alongside each screen. They're the largest single cost here.
- **Mod combinations.** We've tested each hack alone, all 28 together, and the randomizer's presets, but not a seed with hacks on top. Such a disc is labelled "each part tested alone"; step 8 adds one combined test (a casual seed with every hack) and anything it finds gets its own issue.
- **Hacks as separate patches.** The editor builds a selection of hacks together. If any tested hack's bytes depend on which others are chosen, it can't ship as its own patch; criterion 13 catches that, and such a hack is left off the checklist.
- **Shipping the editor's bytes.** The patches are SOTN Editor's code (GPL-3.0), credited, and regenerated from a pinned commit. They contain the hacks' new bytes only, never the game's.
- **Disc space.** Three kept images are about 1.6 GB. Switching to an older disc costs about a minute to rebuild.
- **Scope.** This touches every screen and adds the disc library. The four-PR split keeps each reviewable and playable on its own.

## Defaults I chose (reversible)

- Options and Quit are on the main menu beside the four items asked for: a controller needs a way to both.
- Test castles sit at the bottom of Load castle.
- The BIOS moves from the discs list to the menu bar.
- Three built disc images are kept; the rest are recipes, rebuilt when used.
- A castle switches to its own disc without asking.
- The host's mods aren't sent to the joiner: the joiner makes the same disc themselves.
- Alternate Scarlet Symphony is downloaded from its author's release rather than shipped in our installer; its 34 hacks stay out of the checklist until issue 181 tests them.
- The Discord link is mouse-only, like the GitHub one.
- Enemy HP alone is half the co-op figure at every difficulty (50 / 100 / 150 / 200%).
- The installer's folder page is prefilled with `C:\Games`.
- The PlayStation disc is copied into the folder; the PSP and Saturn discs aren't.
- Uninstalling keeps the player's data unless they say otherwise.
- Later is allowed on the update prompt; version mismatches online are already refused with a clear message.
- Saturn characters use the PlayStation portrait, tinted, if the Saturn disc's can't be read.
