"""Which files, and which bytes in them, differ between two disc images (track 1, raw sectors).

    python patcher/discdiff.py a.bin b.bin [--words FILE]

Lists every ISO 9660 file whose contents differ (and files only on one side), with the
number of changed bytes. --words FILE prints that file's changed 32-bit words (offset: a -> b).
Used to see what a mod touches next to what co-op touches (design/M20).
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from check_disc_layout import DATA, SECTOR, files  # noqa: E402


def read_file(data, lba, size):
    return b"".join(data[(lba + i) * SECTOR + DATA:(lba + i) * SECTOR + DATA + 2048]
                    for i in range((size + 2047) // 2048))[:size]


def contents(image):
    data = Path(image).read_bytes()
    return {path.split(";")[0]: read_file(data, lba, size) for path, (lba, size) in files(Path(image)).items()}


def changed_words(a, b):
    n = min(len(a), len(b)) // 4 * 4
    return [(i, a[i:i + 4], b[i:i + 4]) for i in range(0, n, 4) if a[i:i + 4] != b[i:i + 4]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--words", action="append", default=[])
    args = ap.parse_args()
    fa, fb = contents(args.a), contents(args.b)
    for path in sorted(set(fa) | set(fb)):
        if path not in fa or path not in fb:
            print(f"{path}: only in {'a' if path in fa else 'b'}")
        elif fa[path] != fb[path]:
            diff = sum(x != y for x, y in zip(fa[path], fb[path])) + abs(len(fa[path]) - len(fb[path]))
            print(f"{path}: {diff} bytes differ" + (f" (size {len(fa[path])} -> {len(fb[path])})" if len(fa[path]) != len(fb[path]) else ""))
    for path in args.words:
        for off, x, y in changed_words(fa[path], fb[path]):
            print(f"  {path}+{off:#07x}: {x.hex()} -> {y.hex()}")


if __name__ == "__main__":
    main()
