#!/usr/bin/env python3
"""Fetches what players send the project's mailbox over IMAP, each email once (Gmail label
"fetched"; --all fetches the labelled ones again):
- Bug reports from the app, into local/reports/<name>/ unpacked (git-ignored), with the
  player's note as note.txt. Reports sent in parts (launcher/report.py's parts()) are joined first.
- Reddit's emails for replies to our posts and comments, and mentions, into
  local/reddit/<date>-<user>.txt: who, the post, the comment and its link. Reddit's digests
  and recommendations are skipped.

  fetch_reports.py [--since 2026/11/20] [--all] [--dry-run]
 The login is the first two lines of
~/.config/sotn-coop/gmail-imap.txt: the address, then a Gmail app password (never in the repo).
"""
import argparse
import email
import email.utils
import html
import imaplib
import re
import sys
import urllib.parse
import zipfile
from email.header import decode_header
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGIN = Path.home() / ".config/sotn-coop/gmail-imap.txt"
OUT = ROOT / "local/reports"
REDDIT = ROOT / "local/reddit"
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
    raw = "from:redditmail.com" + ("" if a.all else f" -label:{LABEL}") + (f" after:{a.since}" if a.since else "")
    _, rids = imap.search(None, f'X-GM-RAW "{raw}"')
    rids = rids[0].split()
    print(f"{len(rids)} Reddit email(s)")
    try:
        fetch_reddit(imap, rids, a.dry_run)  # first: they're small, and a big report can be slow
        fetch(imap, ids, a.dry_run)
    except imaplib.IMAP4.abort as e:  # Gmail's daily IMAP limits: the rest come next time
        print(f"stopped: {e}")
        return
    imap.logout()


REPLY = re.compile(r"u/(\S+) (replied to your (?:post|comment)|mentioned you)")


def html_of(msg):
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
    return ""


def text(fragment):
    return html.unescape(re.sub(r"<[^>]+>", "", fragment)).strip()


def reddit_reply(msg):
    """(user, what, post title, comment, link) of a Reddit reply or mention email, or None."""
    m = REPLY.search(text_of(msg["Subject"]))
    if not m:
        return None
    body = html_of(msg)
    spans = [text(t) for t in re.findall(r'<span class="link c-dark-4" dir="auto"[^>]*>(.*?)</span>', body, re.S)]
    link = ""
    for href in re.findall(r'href="https://click\.redditmail\.com/CL0/([^/"]+)', body):
        url = urllib.parse.unquote(href).split("?")[0]
        if re.search(r"/comments/\w+/\w+/\w+/?$", url):
            link = url
            break
    if not spans:  # the layout changed: the preview line still has the comment
        preview = re.search(r'class="preview-text"[^>]*>(.*?)</span>', body, re.S)
        spans = [text(preview.group(1)) if preview else ""]
    return m.group(1), m.group(2), spans[0] if len(spans) > 1 else "", spans[-1], link


def fetch_reddit(imap, ids, dry):
    for i in ids:
        _, data = imap.fetch(i, "(BODY.PEEK[])")
        msg = email.message_from_bytes(data[0][1])
        reply = reddit_reply(msg)
        if reply:
            user, what, post, comment, link = reply
            when = email.utils.parsedate_to_datetime(msg["Date"]).strftime("%Y%m%d-%H%M%S")
            print(f"reddit {when} u/{user} ({what}): {comment[:100]}")
            if not dry:
                REDDIT.mkdir(parents=True, exist_ok=True)
                (REDDIT / f"{when}-{user}.txt").write_text(
                    f"u/{user} {what}\n{msg['Date']}\nPost: {post}\n{link}\n\n{comment}\n")
        if not dry:
            imap.store(i, "+X-GM-LABELS", LABEL)


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
