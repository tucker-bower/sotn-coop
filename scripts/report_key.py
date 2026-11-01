"""Puts the key for F9's Send button in a build, from [api_keys] in env.toml (never committed: D144).

    report_key.py <out file>

With no key it writes nothing, and that build tells players to email their report by hand."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "harness"))
from coop_env import ENV  # noqa: E402

key = ENV.get("api_keys", {}).get("sotncoop_resend_key", "")
if key:
    Path(sys.argv[1]).write_text(key + "\n")
    print("the report key is in the build")
else:
    print("WARNING: no [api_keys] sotncoop_resend_key in env.toml: this build can't send reports", file=sys.stderr)
