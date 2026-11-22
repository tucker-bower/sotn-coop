#!/usr/bin/env python3
"""Puts a bug report sent in parts back together (launcher/report.py's parts()): every
`<name>.zip.partK-of-N` beside the first one given, in order, becomes `<name>.zip`.

  join_report.py <one part>... [--out <folder>]
"""
import argparse
import re
import zipfile
from pathlib import Path


def join(part, out=None):
    m = re.fullmatch(r"(.+\.zip)\.part\d+-of-(\d+)", Path(part).name)
    if not m:
        raise SystemExit(f"{part}: not a report part (<name>.zip.partK-of-N)")
    name, n = m.group(1), int(m.group(2))
    files = [Path(part).with_name(f"{name}.part{k}-of-{n}") for k in range(1, n + 1)]
    missing = [f.name for f in files if not f.exists()]
    if missing:
        raise SystemExit(f"missing: {', '.join(missing)}")
    dest = Path(out or Path(part).parent) / name
    dest.write_bytes(b"".join(f.read_bytes() for f in files))
    zipfile.ZipFile(dest).testzip()  # whole, or this raises
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("parts", nargs="+")
    ap.add_argument("--out")
    a = ap.parse_args()
    for p in a.parts:
        print(join(p, a.out))


if __name__ == "__main__":
    main()
