import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from oficina.config import ROOT
from oficina.domain.exceptions import CarregamentoError, PersistenciaError, ValidacaoError

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    @contextmanager
    def transaction(self, write: bool = False):
        connection = None
        try:
            connection = self.connect()
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            yield connection
            connection.commit()
        except sqlite3.IntegrityError as exc:
            if connection:
                connection.rollback()
            if "UNIQUE" in str(exc):
                raise ValidacaoError(
                    "Registro duplicado: confira CPF, placa, login ou operação já registrada."
                ) from exc
            raise ValidacaoError(
                "O registro possui vínculos ou dados incompatíveis com a operação."
            ) from exc
        except (sqlite3.Error, OSError) as exc:
            if connection:
                connection.rollback()
            logger.exception("Falha no banco de dados")
            error = PersistenciaError if write else CarregamentoError
            message = "salvar" if write else "carregar"
            raise error(f"Não foi possível {message} os dados. Tente novamente.") from exc
        finally:
            if connection:
                connection.close()

    def migrate(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.transaction(write=True) as connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY)"
                )
                for path in sorted((ROOT / "migrations").glob("*.sql")):
                    if connection.execute(
                        "SELECT 1 FROM schema_migrations WHERE version=?", (path.name,)
                    ).fetchone():
                        continue
                    # Não usar executescript: ele encerra implicitamente a transação.
                    statement = ""
                    for line in path.read_text(encoding="utf-8").splitlines(True):
                        statement += line
                        if sqlite3.complete_statement(statement):
                            connection.execute(statement)
                            statement = ""
                    if statement.strip():
                        raise PersistenciaError("Migração incompleta.")
                    connection.execute("INSERT INTO schema_migrations VALUES (?)", (path.name,))
        except OSError as exc:
            raise PersistenciaError("Não foi possível criar ou atualizar o banco.") from exc
