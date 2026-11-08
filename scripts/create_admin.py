import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from oficina.application.auth_service import AuthService  # noqa: E402
from oficina.config import database_path  # noqa: E402
from oficina.domain.exceptions import OficinaError  # noqa: E402
from oficina.infrastructure.database import Database  # noqa: E402

if __name__ == "__main__":
    try:
        database = Database(database_path())
        database.migrate()
        name = input("Nome: ")
        login = input("Login: ")
        password = getpass.getpass(
            "Senha (mínimo de 8 caracteres, uma maiúscula, uma minúscula e um caractere especial): "
        )
        if password != getpass.getpass("Confirme a senha: "):
            raise OficinaError("As senhas não coincidem.")
        AuthService(database).bootstrap(name, login, password)
        print("Administrador criado.")
    except OficinaError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
