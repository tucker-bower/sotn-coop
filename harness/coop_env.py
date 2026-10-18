"""Loads the co-op environment manifest: env.example.toml defaults, overridden by env.toml."""

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
    """Resolves a manifest path (relative to mods/co-op/) to an absolute Path."""
    return (COOP / p).resolve()


ENV = load()
REPO = path(ENV["paths"]["repo"])
DISKS = path(ENV["paths"]["disks"])
ENV_DIR = path(ENV["paths"]["env"])
TOOLS = {k: path(v) for k, v in ENV["tools"].items()}
