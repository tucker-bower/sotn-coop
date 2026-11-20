"""The partner's own sounds that this game's sound memory doesn't hold (#344).

A PlayStation game keeps one character's sound bank in sound memory (VAB 1: Alucard's, or
Richter's; VAB 2: Alucard's familiar's, or Richter's and Maria's second bank). A partner of another
character asks for sounds from its own bank, which here would play this player's sounds instead,
so the game hands them to the host (link.h CoopSfxOut, module/partner.c SoundOut). The host plays
them from the partner character's bank, read from the player's disc (Alucard's SD_ALK, Richter's
SD_RIH, SD_MAR) or the character's blob in the game's memory (the Marias), into the game's own
sound for that frame. The notes are decoded as the app's menus decode theirs (launcher/gamesound.py).

Host-side and timing-free: the game decides which sounds and when; this only renders them."""

import struct
import sys
from array import array
from pathlib import Path

SFX_OUT_ADDR = 0x80800400
SFX_OUT_MAX = 16
CHAR_BLOB_ADDR, CHAR_BLOB_MAGIC = 0x80300000, 0x52414843
CHAR_ALUCARD, CHAR_RICHTER, CHAR_MARIA, CHAR_ULT_MARIA, CHAR_SAT_MARIA, CHAR_ULT_RICHTER = range(6)
_DISC_BANKS = {(CHAR_ALUCARD, 1): "VAB/SD_ALK", (CHAR_RICHTER, 1): "VAB/SD_RIH", (CHAR_ULT_RICHTER, 1): "VAB/SD_RIH"}
MAX_VOICES = 8


def _gamesound():
    here = Path(__file__).resolve().parent.parent / "launcher"
    if str(here) not in sys.path:
        sys.path.append(str(here))
    import gamesound
    return gamesound


def _align(n):
    return (n + 3) & ~3


class PartnerVoices:
    def __init__(self, adapter, disc):
        self.adapter, self.disc = adapter, disc
        self.banks = {}     # (character, vab) -> gamesound.Bank, or None (none to be had)
        self.cache = {}     # a sound's key -> its samples (array of 16-bit, 44.1 kHz mono)
        self.voices = []    # [samples, position, left gain, right gain]
        self.last_frame = None
        self.played = 0     # sounds started (tests)
        self.missing = 0    # sounds with no bank or tone to play them from
        self.heard = set()  # every sound's key handed over (tests)

    def _bank(self, chr_, vab):
        key = (chr_, vab)
        if key not in self.banks:
            self.banks[key] = None
            try:
                self.banks[key] = self._load(chr_, vab)
            except Exception:  # noqa: BLE001 - no bank: those sounds stay silent, as before
                pass
        return self.banks[key]

    def _load(self, chr_, vab):
        gs = _gamesound()
        if chr_ in (CHAR_MARIA, CHAR_ULT_MARIA, CHAR_SAT_MARIA):
            return self._blob_bank(gs, chr_, vab)
        name = _DISC_BANKS.get((chr_, vab)) or ("VAB/SD_MAR" if vab == 2 and chr_ != CHAR_ALUCARD else None)
        if not name or not self.disc:
            return None
        from gameart import disc_files
        files = disc_files(self.disc, [name + ".VH", name + ".VB"])
        if len(files) < 2:
            return None
        return gs.Bank(files[name + ".VH"], files[name + ".VB"])

    def _blob_bank(self, gs, chr_, vab):
        """A Maria's bank from her blob, as the launcher put it in the game's memory (link.h CharBlob)."""
        read = self.adapter.read_bytes
        at = CHAR_BLOB_ADDR
        for _ in range(4):
            magic, character, ovl, vh, vb, partner, vh2, vb2 = struct.unpack("<8I", read(at, 0x20))
            if magic != CHAR_BLOB_MAGIC:
                return None
            head = at + 0x20 + _align(ovl)
            second = head + _align(vh) + _align(vb) + _align(partner)
            if character == chr_:
                if vab == 1 and vh and vb:
                    return gs.Bank(read(head, vh), read(head + _align(vh), vb))
                if vab == 2 and vh2 and vb2:
                    return gs.Bank(read(second, vh2), read(second + _align(vh2), vb2))
                return None
            at = second + _align(vh2) + _align(vb2)
        return None

    def poll(self, render=True):
        """After each frame: the sounds the game handed over this frame, started."""
        frame, n = struct.unpack("<II", self.adapter.read_bytes(SFX_OUT_ADDR, 8))
        if frame == self.last_frame or not 0 < n <= SFX_OUT_MAX:
            self.last_frame = frame
            return
        self.last_frame = frame
        raw = self.adapter.read_bytes(SFX_OUT_ADDR + 8, n * 8)
        for i in range(n):
            chr_, vab, prog, tone, note, vol, pan, _ = struct.unpack_from("<6Bbx", raw, i * 8) + (0,)
            self.played += 1
            self.heard.add((chr_, vab, prog, tone, note, vol))
            if not render:
                continue
            samples = self._render(chr_, vab, prog, tone, note, vol)
            if not samples:
                self.missing += 1
                continue
            pan = max(-8, min(8, pan))
            left, right = min(1.0, (8 - pan) / 8), min(1.0, (8 + pan) / 8)
            self.voices.append([samples, 0, left, right])
            del self.voices[:-MAX_VOICES]

    def check(self):
        """(sounds handed over, kinds, kinds that render to sound): tests."""
        return self.played, len(self.heard), sum(1 for k in self.heard if len(self._render(*k)) > 441)

    def mix_check(self):
        """The loudest sample when the sounds handed over so far are mixed into a silent frame (tests)."""
        voices, self.voices = self.voices, [[self._render(*k), 0, 1.0, 1.0] for k in self.heard]
        out = array("h")
        out.frombytes(self.mix(bytes(735 * 4)))
        self.voices = voices
        return max((abs(v) for v in out), default=0)

    def _render(self, *key):
        if key not in self.cache:
            chr_, vab, prog, tone, note, vol = key
            bank = self._bank(chr_, vab)
            floats = bank.note(prog, tone, note, vol) if bank else []
            self.cache[key] = array("h", (max(-32768, min(32767, int(v * 32767))) for v in floats))
        return self.cache[key]

    def mix(self, audio):
        """This frame's sound (stereo 16-bit), with the partner's voices in it."""
        if not self.voices or not audio:
            return audio
        out = array("h")
        out.frombytes(audio)
        frames = len(out) // 2
        for v in self.voices:
            samples, at, left, right = v
            n = min(frames, len(samples) - at)
            for i in range(n):
                s = samples[at + i]
                a, b = out[2 * i] + int(s * left), out[2 * i + 1] + int(s * right)
                out[2 * i] = 32767 if a > 32767 else -32768 if a < -32768 else a
                out[2 * i + 1] = 32767 if b > 32767 else -32768 if b < -32768 else b
            v[1] = at + n
        self.voices = [v for v in self.voices if v[1] < len(v[0])]
        return out.tobytes()
