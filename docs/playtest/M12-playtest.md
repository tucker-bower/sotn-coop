# Playtest 0.12.0-dev (M12): what to try

**Builds:**
- **PC:** `Emulators\SOTN-Coop-release\SOTN-Coop-setup-0.12.0-dev.exe`, already installed on the PC (2026-10-27).
- **Thor:** `.env/android/SOTN-Coop-0.12.0-dev.apk`. Plug it in with USB debugging on and the agent installs it (`android/device.py install`).

Both players need 0.12.0-dev; the link version changed.

1. **Start-up:** start a game. "Starting the game" should show instead of a long black screen, and the first picture should come about 10 s sooner.
2. **The prologue together:** a new game, online or couch.
   - Both Richters see the opening scene together, and fight one Dracula.
   - After the fight, both see the ending at the same time.
   - At the castle entrance, Death's scene waits for whoever is behind, and both lose their gear.
3. **Leaving:** close the app on one side. The other says "Your partner left the game" straight away.
4. **Off-hand weapons (Richter or Maria):** put a weapon in the free hand in Alucard's equip menu and press ○. It should swing exactly as in Alucard's hands, with the same animation, timing and specials (try a katana, a brand sword, the Heaven Sword). Known: some frames are the wrong colour (a blue blade).
5. **Maria's guardians:** with a weapon or shield in her other hand, her birds stay birds. Throw them standing; they can't be thrown while she's moving or jumping, as in DXC.
6. **Partner's attacks:** in the same room, your partner's subweapons (dagger, axe...), spells and Richter's whip show on your screen. Their hand-weapon swings don't yet.
7. **Debug starts (Developer › Debug starts):** Bosses, **Scenes** and Places, each with that point's level and gear. The Scenes: Maria in the Alchemy Lab, Maria in the Royal Chapel, the Castle Keep. The Librarian now works from his start (walk left: he greets you, then his shop opens). **Please check Maria in the Center the real way:** go into the Center through its door on her floor; she should talk and give you the Holy Glasses, and you should get control back. Her debug start doesn't finish the scene yet.

F9 saves a report whenever something looks wrong.

### For 1.0 (2026-10-27)
- **The Lesser Demon, Olrox and Richter:** after you beat each one, the fight should end normally (music, the way on opens). The automated run can't check these three the way the game does (its bot can't land their last hit).
- **Maria in the Center:** see item 7.
- **Richter or Maria with the Gravity Boots:** try a high ledge Alucard reaches with his super jump (a decision is open on how high theirs should go: STATUS).
