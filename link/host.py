"""One host per game. Call after_frame() once per emulated frame, while the emulator is paused."""

from .mailbox import EVENT_SIZE, Presence
from .transport import TAG_ACK, TAG_EVENTS, TAG_PRESENCE, ReliableChannel


class Host:
    def __init__(self, mailbox, transport):
        self.mailbox, self.transport = mailbox, transport
        self.events = ReliableChannel(transport, EVENT_SIZE)
        self._inbox = []  # partner events the game's in ring had no room for yet
        self._latest_seq = 0
        self.sent = self.received = 0
        self.events_sent = self.events_received = 0

    def after_frame(self):
        if not self.mailbox.ready():  # module not loaded yet (boot), or a different module
            return
        self.transport.send(TAG_PRESENCE, self.mailbox.self_presence().pack())
        self.sent += 1
        mine = self.mailbox.take_events()
        self.events.queue(mine)
        self.events_sent += len(mine)

        latest, reliable = None, []
        for tag, seq, payload in self.transport.receive():
            if tag == TAG_PRESENCE and seq > self._latest_seq:  # UDP may reorder: keep the newest
                self._latest_seq, latest = seq, payload
            elif tag in (TAG_EVENTS, TAG_ACK):
                reliable.append((tag, seq, payload))
        if latest is not None:
            self.mailbox.write_partner(Presence.unpack(latest))
            self.received += 1
        theirs = self.events.tick(reliable)
        self.events_received += len(theirs)
        self._inbox += theirs
        if self._inbox:
            n = self.mailbox.give_events(self._inbox)
            self._inbox = self._inbox[n:]
