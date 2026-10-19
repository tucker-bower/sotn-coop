"""The co-op link: everything between a running game and its partner (design/M1-link-presence.md).

    adapter.py    the emulator interface (the only emulator-specific code)
    mailbox.py    the game <-> host mailbox in RAM (mirrors module/link.h)
    transport.py  messages between the two hosts
    host.py       one per game: moves presence between its mailbox and the partner
"""
