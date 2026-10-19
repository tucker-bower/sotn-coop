"""One host per game. Call after_frame() once per emulated frame, while the emulator is paused."""

from .mailbox import Presence
from .transport import TAG_PRESENCE


class Host:
    def __init__(self, mailbox, transport):
        self.mailbox, self.transport = mailbox, transport
        self._latest_seq = 0
        self.sent = self.received = 0

    def after_frame(self):
        if not self.mailbox.ready():  # module not loaded yet (boot), or a different module
            return
        self.transport.send(TAG_PRESENCE, self.mailbox.self_presence().pack())
        self.sent += 1
        latest = None
        for tag, seq, payload in self.transport.receive():
            if tag == TAG_PRESENCE and seq > self._latest_seq:  # UDP may reorder: keep the newest
                self._latest_seq, latest = seq, payload
        if latest is not None:
            self.mailbox.write_partner(Presence.unpack(latest))
            self.received += 1
