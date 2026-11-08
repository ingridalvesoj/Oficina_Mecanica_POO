import secrets

from oficina.domain import validators as v
from oficina.domain.enums import Perfil
from oficina.domain.exceptions import EstadoInvalidoError, PermissaoNegadaError
from oficina.infrastructure.repositories import Repository
from oficina.infrastructure.security import hash_password, verify_password

from .base import Service

# Mesmo custo de verificação para login inexistente; nunca é uma credencial utilizável.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(24) + "!")


class AuthService(Service):
    def bootstrap(self, nome: str, login: str, password: str) -> int:
        nome = v.required(nome, "o nome")
        login = v.required(login, "o login").casefold()
        password_hash = hash_password(password)
        with self.database.transaction(write=True) as c:
            if c.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone():
                raise EstadoInvalidoError("A configuração inicial já foi realizada.")
            return c.execute(
                "INSERT INTO usuarios(nome,login,senha_hash,perfil) VALUES (?,?,?,?)",
                (nome, login, password_hash, Perfil.ADMIN),
            ).lastrowid

    def has_users(self) -> bool:
        with self.database.transaction() as c:
            return c.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone() is not None

    def login(self, login: str, password: str):
        login = v.required(login, "o login").casefold()
        v.required(password, "a senha")
        with self.database.transaction() as c:
            row = c.execute("SELECT * FROM usuarios WHERE login=?", (login,)).fetchone()
            valid = verify_password(password, row["senha_hash"] if row else _DUMMY_HASH)
            if not row or not valid or not row["ativo"]:
                raise PermissaoNegadaError("Login ou senha inválidos, ou usuário inativo.")
            return Repository(c).user(row["id"])

    def current(self, actor_id: int):
        with self.database.transaction() as c:
            return self.actor(c, actor_id)
