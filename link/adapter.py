"""The emulator interface. Everything emulator-specific in the link goes through one of these,
so choosing the emulator we ship for (R1) means adding an adapter, not changing the host."""

from typing import Protocol


class EmulatorAdapter(Protocol):
    def read_bytes(self, address: int, size: int) -> bytes: ...
    def write_bytes(self, address: int, data: bytes) -> None: ...


class HarnessAdapter:
    """Our SwanStation harness (harness/emu.py). Frames are stepped by the harness itself."""

    def __init__(self, emu):
        self.emu = emu

    def read_bytes(self, address, size):
        return self.emu.read_bytes(address, size)

    def write_bytes(self, address, data):
        a = address & self.emu._ram_mask
        self.emu.ram[a:a + len(data)] = data
