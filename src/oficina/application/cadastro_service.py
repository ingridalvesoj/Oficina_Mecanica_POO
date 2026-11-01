from oficina.domain import validators as v
from oficina.domain.enums import Perfil
from oficina.domain.exceptions import EstadoInvalidoError, ValidacaoError
from oficina.infrastructure.repositories import Repository
from oficina.infrastructure.security import hash_password

from .base import Service

CATALOGS = {"clientes", "veiculos", "pecas", "servicos", "usuarios"}


class CadastroService(Service):
    def list(self, actor_id: int, table: str, active_only: bool = False) -> list[dict]:
        if table not in CATALOGS:
            raise ValidacaoError("Cadastro desconhecido.")
        with self.database.transaction() as c:
            self.actor(c, actor_id, admin=True)
            fields = "id,nome,login,perfil,ativo" if table == "usuarios" else "*"
            where = " WHERE ativo=1" if active_only else ""
            return [
                dict(r) for r in c.execute(f"SELECT {fields} FROM {table}{where} ORDER BY id DESC")
            ]

    def get(self, actor_id: int, table: str, record_id: int):
        if table not in CATALOGS:
            raise ValidacaoError("Cadastro desconhecido.")
        with self.database.transaction() as c:
            self.actor(c, actor_id, admin=True)
            repository = Repository(c)
            return (
                repository.user(record_id)
                if table == "usuarios"
                else repository.entity(table, record_id)
            )

    def save(self, actor_id: int, table: str, data: dict, record_id: int | None = None) -> int:
        if table not in CATALOGS:
            raise ValidacaoError("Cadastro desconhecido.")
        with self.database.transaction(write=True) as c:
            self.actor(c, actor_id, admin=True)
            repo = Repository(c)
            previous = repo.get(table, record_id) if record_id else None
            if table == "clientes":
                values = dict(
                    nome=v.required(data.get("nome"), "o nome do cliente"),
                    cpf=v.cpf(data.get("cpf")),
                    telefone=str(data.get("telefone", "")).strip(),
                    email=v.email(data.get("email", "")),
                )
            elif table == "veiculos":
                owner = repo.get("clientes", data.get("cliente_id"))
                if not previous or previous["cliente_id"] != owner["id"]:
                    self.active(owner, "O cliente")
                if previous and previous["cliente_id"] != owner["id"]:
                    if c.execute(
                        "SELECT 1 FROM ordens_servico WHERE veiculo_id=? AND status NOT IN ('Concluída','Cancelada')",
                        (record_id,),
                    ).fetchone():
                        raise EstadoInvalidoError(
                            "Finalize as OS em andamento antes de transferir o veículo."
                        )
                values = dict(
                    cliente_id=owner["id"],
                    placa=v.plate(data.get("placa")),
                    marca=v.required(data.get("marca"), "a marca"),
                    modelo=v.required(data.get("modelo"), "o modelo"),
                    ano=v.year(data.get("ano")),
                )
            elif table in {"pecas", "servicos"}:
                values = dict(
                    descricao=v.required(data.get("descricao"), "a descrição"),
                    valor_centavos=v.integer(data.get("valor_centavos"), "Valor em centavos"),
                )
            else:
                try:
                    profile = Perfil(data.get("perfil"))
                except (ValueError, TypeError):
                    raise ValidacaoError("Selecione um perfil válido.") from None
                values = dict(
                    nome=v.required(data.get("nome"), "o nome"),
                    login=v.required(data.get("login"), "o login").casefold(),
                    perfil=profile,
                )
                if not previous or data.get("senha"):
                    values["senha_hash"] = hash_password(data.get("senha", ""))
                if previous and previous["perfil"] != profile:
                    self._protect_user(c, previous)
            if previous:
                fields = ",".join(f"{key}=?" for key in values)
                c.execute(f"UPDATE {table} SET {fields} WHERE id=?", (*values.values(), record_id))
                return record_id
            fields = ",".join(values)
            marks = ",".join("?" for _ in values)
            return c.execute(
                f"INSERT INTO {table} ({fields}) VALUES ({marks})", tuple(values.values())
            ).lastrowid

    @staticmethod
    def _protect_user(c, user):
        if user["perfil"] == Perfil.ADMIN and user["ativo"]:
            if (
                c.execute(
                    "SELECT COUNT(*) FROM usuarios WHERE perfil=? AND ativo=1", (Perfil.ADMIN,)
                ).fetchone()[0]
                <= 1
            ):
                raise EstadoInvalidoError(
                    "Não é possível remover ou alterar o último administrador ativo."
                )
        if c.execute(
            "SELECT 1 FROM ordens_servico WHERE mecanico_id=? AND status NOT IN ('Concluída','Cancelada')",
            (user["id"],),
        ).fetchone():
            raise EstadoInvalidoError(
                "Reatribua ou finalize as OS deste mecânico antes da alteração."
            )

    def set_active(self, actor_id: int, table: str, record_id: int, active: bool):
        if table not in CATALOGS:
            raise ValidacaoError("Cadastro desconhecido.")
        with self.database.transaction(write=True) as c:
            self.actor(c, actor_id, admin=True)
            row = Repository(c).get(table, record_id)
            if not active and table == "usuarios":
                self._protect_user(c, row)
            if not active and table in {"clientes", "veiculos"}:
                fk = "cliente_id" if table == "clientes" else "veiculo_id"
                if c.execute(
                    f"SELECT 1 FROM ordens_servico WHERE {fk}=? AND status NOT IN ('Concluída','Cancelada')",
                    (record_id,),
                ).fetchone():
                    raise EstadoInvalidoError(
                        "Finalize as OS em andamento antes de inativar este cadastro."
                    )
            c.execute(f"UPDATE {table} SET ativo=? WHERE id=?", (int(active), record_id))

    def delete(self, actor_id: int, table: str, record_id: int):
        if table not in CATALOGS:
            raise ValidacaoError("Cadastro desconhecido.")
        with self.database.transaction(write=True) as c:
            self.actor(c, actor_id, admin=True)
            row = Repository(c).get(table, record_id)
            if table == "usuarios":
                self._protect_user(c, row)
            if (
                table == "clientes"
                and c.execute(
                    "SELECT 1 FROM ordens_servico WHERE cliente_id=?", (record_id,)
                ).fetchone()
            ):
                raise EstadoInvalidoError(
                    "Cliente com histórico não pode ser excluído. Utilize a inativação."
                )
            c.execute(f"DELETE FROM {table} WHERE id=?", (record_id,))
