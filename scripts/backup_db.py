"""Backup consistente, incluindo transações confirmadas do SQLite."""

import argparse
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from oficina.config import database_path  # noqa: E402

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("destino", type=Path)
    args = parser.parse_args()
    if args.destino.exists():
        parser.error(
            "O destino já existe. Escolha um novo arquivo para preservar o backup anterior."
        )
    if not database_path().exists():
        parser.error("O banco de origem ainda não existe.")
    args.destino.parent.mkdir(parents=True, exist_ok=True)
    source = sqlite3.connect(database_path().as_uri() + "?mode=ro", uri=True)
    target = sqlite3.connect(args.destino)
    try:
        source.backup(target)
    finally:
        target.close()
        source.close()
    print(f"Backup criado: {args.destino}")
