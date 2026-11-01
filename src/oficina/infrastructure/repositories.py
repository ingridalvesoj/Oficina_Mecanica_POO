from oficina.domain.entities import (
    Administrador,
    Cliente,
    ItemPeca,
    ItemServico,
    Mecanico,
    OrdemServico,
    Peca,
    Servico,
    Veiculo,
)
from oficina.domain.enums import Perfil, StatusOS, StatusServico
from oficina.domain.exceptions import RegistroNaoEncontradoError

TABLES = {"usuarios", "clientes", "veiculos", "pecas", "servicos", "ordens_servico"}


class Repository:
    """Repositório vinculado à transação do caso de uso."""

    def __init__(self, connection):
        self.connection = connection

    def get(self, table: str, record_id: int):
        if table not in TABLES:
            raise ValueError("Tabela não permitida")
        row = self.connection.execute(f"SELECT * FROM {table} WHERE id=?", (record_id,)).fetchone()
        if row is None:
            raise RegistroNaoEncontradoError("O registro solicitado não foi encontrado.")
        return row

    def user(self, user_id: int):
        row = self.get("usuarios", user_id)
        cls = Administrador if row["perfil"] == Perfil.ADMIN else Mecanico
        return cls(row["id"], row["nome"], row["login"], bool(row["ativo"]))

    def entity(self, table: str, record_id: int):
        classes = {"clientes": Cliente, "veiculos": Veiculo, "pecas": Peca, "servicos": Servico}
        return classes[table](**dict(self.get(table, record_id)))

    def order(self, order_id: int) -> OrdemServico:
        row = self.get("ordens_servico", order_id)
        parts = [
            ItemPeca(
                r["id"],
                r["peca_id"],
                r["descricao"],
                r["quantidade"],
                r["valor_centavos"],
                bool(r["consumido"]),
            )
            for r in self.connection.execute(
                "SELECT * FROM itens_peca_os WHERE os_id=? ORDER BY id", (order_id,)
            )
        ]
        services = [
            ItemServico(
                r["id"],
                r["servico_id"],
                r["descricao"],
                r["valor_centavos"],
                StatusServico(r["status"]),
            )
            for r in self.connection.execute(
                "SELECT * FROM itens_servico_os WHERE os_id=? ORDER BY id", (order_id,)
            )
        ]
        return OrdemServico(
            row["id"],
            row["cliente_id"],
            row["veiculo_id"],
            row["mecanico_id"],
            row["problema"],
            StatusOS(row["status"]),
            parts,
            services,
        )

    def available(self, part_id: int) -> int:
        part = self.get("pecas", part_id)
        reserved = self.connection.execute(
            """SELECT COALESCE(SUM(i.quantidade),0) FROM itens_peca_os i
            JOIN ordens_servico o ON o.id=i.os_id
            WHERE i.peca_id=? AND i.consumido=0 AND o.status != 'Cancelada'""",
            (part_id,),
        ).fetchone()[0]
        return part["estoque"] - reserved
