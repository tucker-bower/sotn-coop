"""Loads the co-op environment manifest: env.example.toml defaults, overridden by env.toml."""

import os
import tomllib
from pathlib import Path

COOP = Path(__file__).resolve().parent.parent


def _merge(base, over):
    for k, v in over.items():
        base[k] = _merge(base.get(k, {}), v) if isinstance(v, dict) and isinstance(base.get(k), dict) else v
    return base


def load():
    env = tomllib.loads((COOP / "env.example.toml").read_text())
    local = COOP / "env.toml"
    if local.exists():
        _merge(env, tomllib.loads(local.read_text()))
    return env


def path(p):
    """Resolves a manifest path (relative to the co-op root) to an absolute Path."""
    return (COOP / p).resolve()


def _resolve_repo(env):
    p = path(env["paths"]["repo"])
    if not (p / "sotn.sh").exists() and not (p / "config").exists() and (COOP.parent.parent / "sotn.sh").exists():
        return COOP.parent.parent.resolve()
    return p


def _resolve_disks(env, repo):
    p = path(env["paths"]["disks"])
    if not p.exists() and (repo / "disks").exists():
        return (repo / "disks").resolve()
    return p


ENV = load()
REPO = _resolve_repo(ENV)
DISKS = _resolve_disks(ENV, REPO)
ENV_DIR = path(ENV["paths"]["env"])
TOOLS = {k: path(v) for k, v in ENV["tools"].items()}


# COOP_BIOS=path/to/bios.bin runs every game on that BIOS instead of the configured one (e.g.
# OpenBIOS, which can be shipped). Savestates hold the BIOS's RAM, so they get their own library.
BIOS = Path(os.environ["COOP_BIOS"]) if os.environ.get("COOP_BIOS") else None


def savestate(disc, name):
    """Savestates only load on the disc image (and BIOS) that made them: keyed by both."""
    key = Path(disc).stem + (f"@{BIOS.stem}" if BIOS else "")
    return TOOLS["savestates"] / key / f"{name}.state"
