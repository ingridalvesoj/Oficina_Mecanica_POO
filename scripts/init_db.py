import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from oficina.config import database_path  # noqa: E402
from oficina.infrastructure.database import Database  # noqa: E402

if __name__ == "__main__":
    database = Database(database_path())
    database.migrate()
    print(f"Banco inicializado: {database.path}")
