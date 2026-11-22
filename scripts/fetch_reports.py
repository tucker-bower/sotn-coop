#!/usr/bin/env python3
"""Fetches the players' emailed bug reports from the project's mailbox over IMAP, into
local/reports/<name>/ unpacked (git-ignored), with the player's note as note.txt. Each fetched
email gets the Gmail label "fetched", so a report is fetched once. Reports sent in parts
(launcher/report.py's parts()) are joined first.

  fetch_reports.py [--since 2026/11/20] [--all] [--dry-run]

--all fetches the labelled ones again. The login is the first two lines of
~/.config/sotn-coop/gmail-imap.txt: the address, then a Gmail app password (never in the repo).
"""
import argparse
import email
import imaplib
import re
import sys
import zipfile
from email.header import decode_header
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGIN = Path.home() / ".config/sotn-coop/gmail-imap.txt"
OUT = ROOT / "local/reports"
LABEL = "fetched"
sys.path.insert(0, str(ROOT / "scripts"))
from join_report import join  # noqa: E402


def text_of(header):
    return "".join(p.decode(c or "utf-8", "replace") if isinstance(p, bytes) else p for p, c in decode_header(header or ""))


def note_of(msg):
    for part in msg.walk():
        if part.get_content_type() == "text/plain" and not part.get_filename():
            return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace").strip()
    return ""


def save(msg, dry):
    """Unpacks one report email; returns its folder, or None if it held no report."""
    subject = text_of(msg["Subject"])
    m = re.search(r"Bug report (\S+(?: \(\d+\))?) \(([^)]+)\)", subject)
    if not m:
        return None
    name, version = m.groups()
    files = {part.get_filename(): part.get_payload(decode=True) for part in msg.walk() if part.get_filename()}
    if not files:
        return None
    dest = OUT / name
    if dry:
        return dest
    dest.mkdir(parents=True, exist_ok=True)
    for fname, data in files.items():
        (dest / Path(fname).name).write_bytes(data)
    zips = [dest / f for f in files if f.endswith(".zip")]
    first = next((dest / f for f in files if re.search(r"\.part1-of-\d+$", f)), None)
    if first:
        zips.append(join(first))
    for z in zips:
        zipfile.ZipFile(z).extractall(dest)
    (dest / "note.txt").write_text(f"{subject}\n{msg['Date']}\n\n{note_of(msg)}\n")
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--since", help="only emails from this day on (YYYY/MM/DD)")
    a = ap.parse_args()
    user, password = LOGIN.read_text().split()[:2]
    imap = imaplib.IMAP4_SSL("imap.gmail.com", timeout=120)
    imap.login(user, password)
    imap.create(LABEL)  # fails harmlessly when it exists
    imap.select("INBOX")
    raw = "subject:(Bug report)" + ("" if a.all else f" -label:{LABEL}") + (f" after:{a.since}" if a.since else "")
    query = f'X-GM-RAW "{raw}"'
    _, ids = imap.search(None, query)
    ids = ids[0].split()
    print(f"{len(ids)} report email(s)")
    try:
        fetch(imap, ids, a.dry_run)
    except imaplib.IMAP4.abort as e:  # Gmail's daily IMAP limits: the rest come next time
        print(f"stopped: {e}")
        return
    imap.logout()


def fetch(imap, ids, dry):
    for i in ids:
        _, data = imap.fetch(i, "(BODY.PEEK[HEADER.FIELDS (SUBJECT)])")
        subject = text_of(email.message_from_bytes(data[0][1])["Subject"])
        m = re.search(r"Bug report (\S+(?: \(\d+\))?) \(", subject)
        if dry or (m and (OUT / m.group(1) / "note.txt").exists()):  # here already: only the label
            print(subject + ("" if dry else ": here already"))
            if not dry:
                imap.store(i, "+X-GM-LABELS", LABEL)
            continue
        _, data = imap.fetch(i, "(BODY.PEEK[])")
        msg = email.message_from_bytes(data[0][1])
        dest = save(msg, dry)
        if dest is None:
            continue
        print(f"{dest.name}: {note_of(msg)[:100]}")
        if not dry:
            imap.store(i, "+X-GM-LABELS", LABEL)


if __name__ == "__main__":
    main()
