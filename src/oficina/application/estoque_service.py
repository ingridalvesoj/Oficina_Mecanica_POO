from oficina.domain import validators as v
from oficina.domain.exceptions import EstoqueInsuficienteError, ValidacaoError
from oficina.infrastructure.repositories import Repository

from .base import Service


class EstoqueService(Service):
    def enter(self, actor_id: int, part_id: int, quantity: int, reason: str = ""):
        return self.move(actor_id, part_id, quantity, "Entrada", reason)

    def withdraw(self, actor_id: int, part_id: int, quantity: int, reason: str = ""):
        return self.move(actor_id, part_id, quantity, "Saída", reason)

    def move(self, actor_id: int, part_id: int, quantity: int, kind: str, reason: str = ""):
        if kind not in {"Entrada", "Saída"}:
            raise ValidacaoError("Selecione entrada ou saída de estoque.")
        quantity = v.integer(quantity, "Quantidade", 1)
        reason = str(reason or "").strip()
        with self.database.transaction(write=True) as c:
            self.actor(c, actor_id, admin=True)
            part = Repository(c).get("pecas", part_id)
            self.active(part, "A peça")
            if kind == "Saída" and Repository(c).available(part_id) < quantity:
                raise EstoqueInsuficienteError(
                    "A saída excede o estoque disponível. Quantidades reservadas não podem ser retiradas."
                )
            delta = quantity if kind == "Entrada" else -quantity
            v.integer(part["estoque"] + delta, "Estoque")
            c.execute("UPDATE pecas SET estoque=estoque+? WHERE id=?", (delta, part_id))
            c.execute(
                "INSERT INTO movimentacoes_estoque(peca_id,usuario_id,tipo,quantidade,justificativa) VALUES (?,?,?,?,?)",
                (part_id, actor_id, kind, quantity, reason),
            )

    def balances(self, actor_id: int) -> list[dict]:
        with self.database.transaction() as c:
            self.actor(c, actor_id, admin=True)
            repo = Repository(c)
            return [
                dict(r) | {"disponivel": repo.available(r["id"])}
                for r in c.execute("SELECT * FROM pecas ORDER BY id")
            ]

    def history(self, actor_id: int) -> list[dict]:
        with self.database.transaction() as c:
            self.actor(c, actor_id, admin=True)
            return [
                dict(r)
                for r in c.execute("""SELECT m.id,p.descricao,m.tipo,m.quantidade,m.os_id,
                u.nome AS responsavel,m.justificativa,m.data FROM movimentacoes_estoque m
                JOIN pecas p ON p.id=m.peca_id JOIN usuarios u ON u.id=m.usuario_id ORDER BY m.id DESC""")
            ]
