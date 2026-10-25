# M9 playtest: Android on the AYN Thor, with cross-play against the PC

**Builds (same code, so they connect):**
- Thor: `.env/android/SOTN-Coop-0.9.0-dev.apk` (arm64 + x86_64, about 39 MB)
- PC: `Emulators\SOTN-Coop-release\SOTN-Coop-setup-0.9.0-dev.exe`. Install it over the older one: older PC builds (0.7.1, 0.8.0-dev) can't play the Thor, and 0.7.1's lobby never starts with some controllers.

## Before: the Thor, once (2 minutes)
1. On the Thor: **Settings › About device**, tap **Build number** 7 times. Then **Settings › System › Developer options**, turn on **USB debugging**.
2. Plug the Thor into the PC. Tap **Allow** when it asks about this computer (tick *Always allow*).
3. Tell the agent. It runs `python android/device.py install` (the app) and `python android/device.py disc` (your disc into `Download/SOTN`, skipping the USB copy step).

No USB debugging? Copy the `.apk` onto the Thor over USB file transfer and tap it in the Files app. Allow installing from Files when Android asks.

## Test
1. **First start:** open **SOTN Co-op** (on the top screen). Tap **Choose my disc's folder** › `Download` › `SOTN` › **Use this folder** › **Allow**. The vial should fill twice (copying, then making the co-op disc), then show *Co-op disc ready*. Controller or touch both work in the menus.
2. **Thor hosts, PC joins:** Thor: **Online co-op › Host: new game**. PC: **Online co-op › Join your partner**, type the Thor's room code. Play a few rooms: puppets, map marker, shared pickups, a joint save.
3. **PC hosts, Thor joins:** the other way round. The Thor types the code (the on-screen keyboard appears).
4. **Handheld checks:**
   - **Back** pauses, and never closes the app.
   - The screen stays on with only the controller in use (10+ minutes).
   - Sound is clean, with no crackle.
   - The game runs at full speed.
5. **Optional:**
   - Maria: **Settings › Game files**, then pick your DXC `.iso`.
   - Try a nested folder: put the rip one folder deeper and pick the outer folder.

## Bugs
Say what happened. The agent pulls the Thor's log with `python android/device.py log` (or press **F9** on the PC side for its report).
