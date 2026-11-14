"""Configuration: one TOML file, found in this order.

1. the path given with --config or the QUOTESIGHT_CONFIG environment variable
2. ./config.toml in the current folder
3. the user config folder: ~/.config/quotesight/config.toml (macOS, Linux)
   or %APPDATA%\\quotesight\\config.toml (Windows)

Relative paths inside the file are resolved against the folder that holds the file.
"""
import os
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

DEFAULTS = {
    "library": {
        "roots": [],
        "topics": "subfolder",
        "topic_pattern": "",
        "exclude": [".trash", ".git", "node_modules"],
        "description": "research papers",
    },
    "index": {
        "data_dir": "./data",
        "chunk_words": 300,
        "max_words": 450,
        "embed_model": "nomic-ai/nomic-embed-text-v1.5",
        "device": "auto",
        "workers": 4,
    },
    "metadata": {
        "crossref": True,
        "mailto": "",
    },
    "llm": {
        "backend": "claude",
        "language": "English",
        "max_passages": 45,
        "max_passages_broad": 75,
        "claude_model": "sonnet",
        "claude_effort": "medium",
        "claude_vocab_model": "haiku",
        "codex_model": "",
        "codex_effort": "medium",
        "codex_vocab_model": "",
    },
    "app": {
        "host": "127.0.0.1",
        "port": 8765,
        "ui_language": "en",
    },
}


def user_config_dir():
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")) / "quotesight"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "quotesight"


def find_config(explicit=None):
    for c in (explicit, os.environ.get("QUOTESIGHT_CONFIG"), Path.cwd() / "config.toml",
              user_config_dir() / "config.toml"):
        if c and Path(c).expanduser().is_file():
            return Path(c).expanduser().resolve()
    return None


def _merge(base, extra):
    out = {k: dict(v) if isinstance(v, dict) else v for k, v in base.items()}
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k].update(v)
        else:
            out[k] = v
    return out


class Config:
    def __init__(self, path=None):
        self.path = find_config(path)
        data = {}
        if self.path:
            with open(self.path, "rb") as f:
                data = tomllib.load(f)
        self.raw = _merge(DEFAULTS, data)
        self.base = self.path.parent if self.path else Path.cwd()

    def __getitem__(self, section):
        return self.raw[section]

    def resolve(self, p):
        p = Path(os.path.expandvars(str(p))).expanduser()
        return (p if p.is_absolute() else self.base / p).resolve()

    @property
    def roots(self):
        return [self.resolve(r) for r in self["library"]["roots"]]

    @property
    def data_dir(self):
        d = self.resolve(self["index"]["data_dir"])
        d.mkdir(parents=True, exist_ok=True)
        return d

    @property
    def db_path(self):
        return self.data_dir / "index.sqlite"


_cfg = None


def get(path=None, reload=False):
    global _cfg
    if _cfg is None or reload or path:
        _cfg = Config(path)
    return _cfg
