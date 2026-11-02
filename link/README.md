# link

Everything between a running game and its partner: the mailbox, netcode and connecting.

| File | What it does |
|---|---|
| `__init__.py` | Package overview. |
| `adapter.py` | The one interface to the emulator. |
| `connect.py` | Finds the partner over the internet from a room code. |
| `host.py` | Runs once per frame for each game: moves data between its mailbox and the partner. |
| `jointsave.py` | Joint saves, on the couch and online. |
| `mailbox.py` | The game-to-host mailbox in RAM; mirrors `module/link.h`. |
| `natsim.py` | A virtual internet with home routers, for connection tests. |
| `netsim.py` | A simulated bad connection, for tests and for trying one at home. |
| `playout.py` | A jitter buffer that plays the partner's state back evenly. |
| `portmap.py` | Asks the home router to open the game's port. |
| `portraits.py` | Reads Richter's and Maria's cutscene portraits from the player's disc for their pause menu. |
| `relay.py` | **Vestigial.** A working relay no release uses or starts (D123); kept for anyone who wants to run one. |
| `rendezvous.py` | Connect codes, STUN and direct-IP parsing. |
| `test_connect.py` | Connects every pair of router types on the virtual internet. |
| `test_portmap.py` | **Manual.** Checks `portmap.py` against fake routers; passes, but no runner includes it. |
| `transport.py` | Messages between hosts over UDP. |
