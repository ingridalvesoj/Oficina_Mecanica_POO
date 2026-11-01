from oficina.domain.enums import Perfil
from oficina.domain.exceptions import PermissaoNegadaError, ValidacaoError
from oficina.infrastructure.repositories import Repository


class Service:
    def __init__(self, database):
        self.database = database

    def actor(self, connection, user_id: int, admin: bool = False):
        # Recarrega perfil e atividade a cada operação: não confiar no estado da UI.
        actor = Repository(connection).user(user_id)
        if not actor.ativo or (admin and actor.perfil != Perfil.ADMIN):
            raise PermissaoNegadaError("Seu perfil não permite esta operação.")
        return actor

    @staticmethod
    def active(row, label: str):
        if not row["ativo"]:
            raise ValidacaoError(f"{label} está inativo. Escolha um cadastro ativo.")
