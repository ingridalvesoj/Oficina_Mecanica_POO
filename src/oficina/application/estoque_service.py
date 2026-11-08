from oficina.domain import validators as v
from oficina.infrastructure.repositories import Repository

from .base import Service


class EstoqueService(Service):
    def enter(self, actor_id: int, part_id: int, quantity: int, reason: str = ""):
        quantity = v.integer(quantity, "Quantidade", 1)
        reason = str(reason or "").strip()
        with self.database.transaction(write=True) as c:
            self.actor(c, actor_id, admin=True)
            part = Repository(c).get("pecas", part_id)
            self.active(part, "A peça")
            v.integer(part["estoque"] + quantity, "Estoque")
            c.execute("UPDATE pecas SET estoque=estoque+? WHERE id=?", (quantity, part_id))
            c.execute(
                "INSERT INTO movimentacoes_estoque(peca_id,usuario_id,tipo,quantidade,justificativa) VALUES (?,?,'Entrada',?,?)",
                (part_id, actor_id, quantity, reason),
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
