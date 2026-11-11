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
| `rendezvous.py` | Connect codes, STUN and direct-IP parsing. |
| `test_connect.py` | Connects every pair of router types on the virtual internet. |
| `test_layout.py` | Checks `mailbox.py`'s offsets, constants and sizes against `module/link.h`. |
| `test_backlog.py` | Events to a partner who isn't there: the host's sending stays flat after the partner leaves, a solo castle keeps none, and an outage loses none (issue 223). |
| `test_malformed.py` | Sends two linked hosts what a partner's game never would: no packet stops a host's frame or fills its memory. |
| `test_portmap.py` | Checks `portmap.py` against fake routers. |
| `transport.py` | Messages between hosts over UDP. |
