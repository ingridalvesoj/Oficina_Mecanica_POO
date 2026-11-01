"""Configuração local independente da interface."""

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def database_path() -> Path:
    configured = Path(os.environ.get("OFICINA_DB", "data/oficina.sqlite3"))
    return configured if configured.is_absolute() else ROOT / configured
