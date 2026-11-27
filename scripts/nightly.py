#!/usr/bin/env python3
"""The nightly maintenance run (design/maintenance-mode.md, D236): fetch the inbox and, when
players sent something new, run a headless Claude Code agent on it, with scripts/nightly_prompt.md.
The agent fixes real bugs (each with a test that fails before and passes after), ships at most
one bug-fix release, and writes local/nightly/<date>.md, which is then emailed to Tucker.

    nightly.py [--dry-run] [--force] [--hours 4]

--dry-run fetches nothing new and starts no agent: it prints what a run would do.
--force runs the agent even with nothing new (it then works the open `bug` issues).
--item reddit/<file> treats that file under local/ as new: a test of the agent's path.

Stops, doing nothing, when local/nightly.stop exists or an open issue is labelled pause-nightly.
Windows Task Scheduler starts it at night (scripts/nightly_schedule.ps1). The summary email goes
from the project mailbox (~/.config/sotn-coop/gmail-imap.txt) to the address in
~/.config/sotn-coop/nightly-to.txt; neither is ever in the repo.
"""
import argparse
import datetime
import fcntl
import smtplib
import subprocess
import sys
from email.message import EmailMessage
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / "local"
OUT = LOCAL / "nightly"
STOP = LOCAL / "nightly.stop"
PROMPT = ROOT / "scripts/nightly_prompt.md"
CONFIG = Path.home() / ".config/sotn-coop"
INBOX = ("reports", "reddit")
# The agent's tools: auto mode decides the rest; these never run unattended.
DENY = ["Bash(git push --force*)", "Bash(git push -f*)", "Bash(git reset --hard*)", "Bash(gh release delete*)",
        "Bash(gh repo*)", "Bash(rm -rf /*)", "Bash(rm -rf ~*)", "Bash(sudo*)"]


def log(msg):
    line = f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} {msg}"
    print(line, flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "nightly.log", "a") as f:
        f.write(line + "\n")


def run(cmd, timeout=None, **kw):
    return subprocess.run(cmd, cwd=ROOT, text=True, capture_output=True, timeout=timeout, **kw)


def paused():
    if STOP.exists():
        return f"{STOP} exists"
    r = run(["gh", "issue", "list", "--label", "pause-nightly", "--state", "open", "--json", "number", "--jq", ".[].number"])
    if r.returncode == 0 and r.stdout.strip():
        return f"issue #{r.stdout.split()[0]} is labelled pause-nightly"
    return None


def inbox():
    return {str(p.relative_to(LOCAL)) for d in INBOX if (LOCAL / d).is_dir() for p in (LOCAL / d).iterdir()}


def clean_main():
    """Puts the worktree on origin/main. Returns why it can't, or None."""
    if run(["git", "status", "--porcelain", "--untracked-files=no"]).stdout.strip():
        return "the worktree has uncommitted changes (another session's work?)"
    run(["git", "fetch", "-q", "origin"])
    r = run(["git", "checkout", "-q", "--detach", "origin/main"])
    return (r.stderr.strip() or "the checkout failed") if r.returncode else None


def email(subject, body):
    try:
        user, password = (CONFIG / "gmail-imap.txt").read_text().split()[:2]
        to = (CONFIG / "nightly-to.txt").read_text().strip()
    except (OSError, ValueError):
        log("no email: ~/.config/sotn-coop/nightly-to.txt or gmail-imap.txt is missing")
        return
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = user, to, subject
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
        s.login(user, password)
        s.send_message(msg)
    log(f"emailed: {subject}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--hours", type=float, default=4)
    ap.add_argument("--item", action="append", default=[], help="treat this file under local/ as new (a test)")
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    lock = open(OUT / "lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log("another nightly run holds the lock")
        return 0
    day = datetime.date.today().isoformat()
    why = paused()
    if why:
        log(f"paused: {why}")
        return 0
    if run([sys.executable, "scripts/disk_space.py"]).returncode:
        log("stopped: not enough disk space")
        email(f"SOTN Co-op nightly {day}: stopped, disk space", "scripts/disk_space.py says there isn't room to build and test.")
        return 1

    before = inbox()
    fetch = [sys.executable, "-u", "scripts/fetch_reports.py"] + (["--dry-run"] if a.dry_run else [])
    try:
        r = run(fetch, timeout=1800)
        log("fetch: " + " / ".join(r.stdout.strip().splitlines()[:2]))
    except subprocess.TimeoutExpired:
        log("fetch timed out after 30 min; going on with what arrived")
    new = sorted((inbox() - before) | set(a.item))
    log(f"{len(new)} new: {', '.join(new) or 'nothing'}")
    if not new and not a.force:
        return 0
    if a.dry_run:
        log("dry run: an agent would start now")
        return 0

    prompt = PROMPT.read_text()  # before the checkout, which may change it
    why = clean_main()
    if why:
        log(f"stopped: {why}")
        email(f"SOTN Co-op nightly {day}: didn't run", f"{len(new)} new item(s) wait in local/, but {why}.\n\n" + "\n".join(new))
        return 1
    summary = OUT / f"{day}.md"
    task = prompt.replace("{DATE}", day).replace("{SUMMARY}", str(summary)) + \
        "\n## Tonight's new items\n" + ("\n".join(f"- local/{n}" for n in new) or "- none (a forced run: work the open `bug` issues)") + "\n"
    cmd = ["claude", "-p", task, "--permission-mode", "auto", "--disallowedTools", *DENY,
           "--add-dir", str(Path.home() / "sotn-coop"), "--output-format", "text"]
    log(f"agent starts ({a.hours} h at most)")
    agent_log = OUT / f"{day}.log"
    with open(agent_log, "w") as f:
        try:
            code = subprocess.run(cmd, cwd=ROOT, stdout=f, stderr=subprocess.STDOUT, timeout=a.hours * 3600).returncode
        except subprocess.TimeoutExpired:
            code = "timed out"
    log(f"agent ended: {code}")
    if summary.exists():
        body = summary.read_text()
    else:
        tail = agent_log.read_text()[-3000:] if agent_log.exists() else ""
        body = f"The agent ended ({code}) without writing a summary. The end of its log ({agent_log}):\n\n{tail}"
    first = next((ln.strip("# ").strip() for ln in body.splitlines() if ln.strip()), "summary")
    email(f"SOTN Co-op nightly {day}: {first[:80]}", body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
