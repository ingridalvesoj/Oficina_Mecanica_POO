from oficina.domain import validators as v
from oficina.domain.enums import Perfil, StatusOS, StatusServico
from oficina.domain.exceptions import (
    EstadoInvalidoError,
    EstoqueInsuficienteError,
    PermissaoNegadaError,
    RegistroNaoEncontradoError,
    ValidacaoError,
)
from oficina.infrastructure.repositories import Repository

from .base import Service


class OrdemService(Service):
    def _access(self, c, actor_id, order_id, action="visualizar"):
        actor = self.actor(c, actor_id)
        order = Repository(c).order(order_id)
        if not actor.permite(action, order.mecanico_id):
            raise PermissaoNegadaError("Seu perfil não permite esta operação nesta OS.")
        return order

    @staticmethod
    def _audit(c, order_id, actor_id, action, reason=""):
        c.execute(
            "INSERT INTO auditoria_os(os_id,usuario_id,acao,justificativa) VALUES (?,?,?,?)",
            (order_id, actor_id, action, reason),
        )

    @staticmethod
    def _status(c, order, target, actor_id, reason=""):
        c.execute("UPDATE ordens_servico SET status=? WHERE id=?", (target, order.id))
        c.execute(
            "INSERT INTO historico_status_os(os_id,usuario_id,anterior,novo,justificativa) VALUES (?,?,?,?,?)",
            (order.id, actor_id, order.status, target, reason),
        )

    @staticmethod
    def _movement(c, actor_id, order_id, part_id, quantity, kind, reason=""):
        c.execute(
            "INSERT INTO movimentacoes_estoque(peca_id,os_id,usuario_id,tipo,quantidade,justificativa) VALUES (?,?,?,?,?,?)",
            (part_id, order_id, actor_id, kind, quantity, reason),
        )

    def create(
        self,
        actor_id: int,
        client_id: int,
        vehicle_id: int,
        problem: str,
        mechanic_id: int | None = None,
    ) -> int:
        problem = v.required(problem, "o problema relatado")
        with self.database.transaction(write=True) as c:
            self.actor(c, actor_id, admin=True)
            repo = Repository(c)
            client, vehicle = repo.get("clientes", client_id), repo.get("veiculos", vehicle_id)
            self.active(client, "O cliente")
            self.active(vehicle, "O veículo")
            if vehicle["cliente_id"] != client_id:
                raise ValidacaoError("O veículo não pertence ao cliente selecionado.")
            if mechanic_id is not None:
                self._mechanic(repo, mechanic_id)
            order_id = c.execute(
                "INSERT INTO ordens_servico(cliente_id,veiculo_id,mecanico_id,problema,status) VALUES (?,?,?,?,?)",
                (client_id, vehicle_id, mechanic_id, problem, StatusOS.ABERTA),
            ).lastrowid
            c.execute(
                "INSERT INTO historico_status_os(os_id,usuario_id,novo) VALUES (?,?,?)",
                (order_id, actor_id, StatusOS.ABERTA),
            )
            return order_id

    @staticmethod
    def _mechanic(repo, mechanic_id):
        mechanic = repo.user(mechanic_id)
        if not mechanic.ativo or mechanic.perfil != Perfil.MECANICO:
            raise ValidacaoError("Selecione um mecânico ativo.")

    def edit(self, actor_id: int, order_id: int, problem: str, mechanic_id: int | None):
        problem = v.required(problem, "o problema relatado")
        with self.database.transaction(write=True) as c:
            order = self._access(c, actor_id, order_id, "administrar")
            order.validar_edicao()
            if mechanic_id is not None:
                self._mechanic(Repository(c), mechanic_id)
            elif order.status == StatusOS.EXECUCAO:
                raise EstadoInvalidoError("Uma OS em execução precisa de mecânico responsável.")
            c.execute(
                "UPDATE ordens_servico SET problema=?,mecanico_id=? WHERE id=?",
                (problem, mechanic_id, order_id),
            )
            self._audit(c, order_id, actor_id, "Dados gerais atualizados")

    def _prepare_items(self, c, actor_id, order_id, reason):
        order = self._access(c, actor_id, order_id, "administrar")
        order.validar_edicao()
        if order.status == StatusOS.EXECUCAO:
            reason = v.required(reason, "a justificativa da alteração durante a execução")
        # Qualquer mudança invalida o orçamento pendente ou já aprovado.
        if order.status in {StatusOS.APROVADA, StatusOS.AGUARDANDO}:
            self._status(
                c,
                order,
                StatusOS.ORCAMENTO,
                actor_id,
                "Itens alterados; nova aprovação necessária.",
            )
        return order, reason

    def add_part(self, actor_id: int, order_id: int, part_id: int, quantity: int, reason=""):
        quantity = v.integer(quantity, "Quantidade", 1)
        with self.database.transaction(write=True) as c:
            order, reason = self._prepare_items(c, actor_id, order_id, reason)
            repo = Repository(c)
            part = repo.get("pecas", part_id)
            self.active(part, "A peça")
            if repo.available(part_id) < quantity:
                raise EstoqueInsuficienteError(
                    "Quantidade solicitada maior que o estoque disponível."
                )
            consumed = order.status == StatusOS.EXECUCAO
            item_id = c.execute(
                "INSERT INTO itens_peca_os(os_id,peca_id,descricao,quantidade,valor_centavos,consumido) VALUES (?,?,?,?,?,?)",
                (
                    order_id,
                    part_id,
                    part["descricao"],
                    quantity,
                    part["valor_centavos"],
                    int(consumed),
                ),
            ).lastrowid
            if consumed:
                c.execute("UPDATE pecas SET estoque=estoque-? WHERE id=?", (quantity, part_id))
            self._movement(
                c,
                actor_id,
                order_id,
                part_id,
                quantity,
                "Consumo" if consumed else "Reserva",
                reason,
            )
            self._audit(
                c,
                order_id,
                actor_id,
                f"Peça adicionada: item {item_id}, quantidade {quantity}",
                reason,
            )
            return item_id

    def add_service(self, actor_id: int, order_id: int, service_id: int, reason=""):
        with self.database.transaction(write=True) as c:
            _, reason = self._prepare_items(c, actor_id, order_id, reason)
            service = Repository(c).get("servicos", service_id)
            self.active(service, "O serviço")
            item_id = c.execute(
                "INSERT INTO itens_servico_os(os_id,servico_id,descricao,valor_centavos) VALUES (?,?,?,?)",
                (order_id, service_id, service["descricao"], service["valor_centavos"]),
            ).lastrowid
            self._audit(c, order_id, actor_id, f"Serviço adicionado: item {item_id}", reason)
            return item_id

    def remove_item(self, actor_id: int, order_id: int, kind: str, item_id: int, reason=""):
        if kind not in {"peca", "servico"}:
            raise ValidacaoError("Tipo de item inválido.")
        table = "itens_peca_os" if kind == "peca" else "itens_servico_os"
        with self.database.transaction(write=True) as c:
            _, reason = self._prepare_items(c, actor_id, order_id, reason)
            item = c.execute(
                f"SELECT * FROM {table} WHERE id=? AND os_id=?", (item_id, order_id)
            ).fetchone()
            if item is None:
                raise RegistroNaoEncontradoError("O item não foi encontrado nesta OS.")
            if kind == "peca":
                if item["consumido"]:
                    raise EstadoInvalidoError(
                        "Peça já consumida não pode ser removida nesta versão."
                    )
                self._movement(
                    c, actor_id, order_id, item["peca_id"], item["quantidade"], "Liberação", reason
                )
            elif item["status"] != StatusServico.PENDENTE:
                raise EstadoInvalidoError("Não é possível remover um serviço já iniciado.")
            c.execute(f"DELETE FROM {table} WHERE id=?", (item_id,))
            self._audit(c, order_id, actor_id, f"Item removido: {kind} {item_id}", reason)

    def transition(self, actor_id: int, order_id: int, target: str, reason=""):
        try:
            target = StatusOS(target)
        except ValueError:
            raise ValidacaoError("Situação da OS inválida.") from None
        with self.database.transaction(write=True) as c:
            action = (
                "executar" if target in {StatusOS.EXECUCAO, StatusOS.CONCLUIDA} else "administrar"
            )
            order = self._access(c, actor_id, order_id, action)
            order.validar_transicao(target)
            if target == StatusOS.CANCELADA:
                reason = v.required(reason, "a justificativa do cancelamento")
                for part in order.pecas:
                    self._movement(
                        c, actor_id, order_id, part.peca_id, part.quantidade, "Liberação", reason
                    )
            if target == StatusOS.EXECUCAO:
                self._mechanic(Repository(c), order.mecanico_id)
                for part in order.pecas:
                    updated = c.execute(
                        "UPDATE pecas SET estoque=estoque-? WHERE id=? AND estoque>=?",
                        (part.quantidade, part.peca_id, part.quantidade),
                    ).rowcount
                    if updated != 1:
                        raise EstoqueInsuficienteError(
                            "Estoque insuficiente para iniciar a execução."
                        )
                    c.execute("UPDATE itens_peca_os SET consumido=1 WHERE id=?", (part.id,))
                    self._movement(c, actor_id, order_id, part.peca_id, part.quantidade, "Consumo")
            if target == StatusOS.CONCLUIDA:
                c.execute(
                    "UPDATE ordens_servico SET data_conclusao=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?",
                    (order_id,),
                )
            self._status(c, order, target, actor_id, reason)

    def update_service(self, actor_id: int, order_id: int, item_id: int, target: str):
        try:
            target = StatusServico(target)
        except ValueError:
            raise ValidacaoError("Situação do serviço inválida.") from None
        with self.database.transaction(write=True) as c:
            order = self._access(c, actor_id, order_id, "executar")
            if order.status != StatusOS.EXECUCAO:
                raise EstadoInvalidoError("Inicie a execução da OS antes de atualizar serviços.")
            item = next((s for s in order.servicos if s.id == item_id), None)
            if item is None:
                raise RegistroNaoEncontradoError("O serviço não foi encontrado nesta OS.")
            allowed = {
                StatusServico.PENDENTE: StatusServico.EXECUCAO,
                StatusServico.EXECUCAO: StatusServico.FINALIZADO,
            }
            if allowed.get(item.status) != target:
                raise EstadoInvalidoError(
                    "Transição de serviço inválida. Inicie antes de finalizar."
                )
            c.execute(
                "UPDATE itens_servico_os SET status=?,data_finalizacao=CASE WHEN ?='Finalizado' THEN strftime('%Y-%m-%dT%H:%M:%SZ','now') ELSE NULL END WHERE id=?",
                (target, target, item_id),
            )
            self._audit(c, order_id, actor_id, f"Serviço {item_id}: {target}")

    def request_change(self, actor_id: int, order_id: int, request: str):
        request = v.required(request, "a solicitação de alteração")
        with self.database.transaction(write=True) as c:
            order = self._access(c, actor_id, order_id, "executar")
            order.validar_edicao()
            self._audit(c, order_id, actor_id, "Solicitação de alteração de itens", request)

    def invoice(self, actor_id: int, order_id: int):
        with self.database.transaction(write=True) as c:
            order = self._access(c, actor_id, order_id, "administrar")
            if order.status != StatusOS.CONCLUIDA:
                raise EstadoInvalidoError("Conclua a OS antes de faturar.")
            if c.execute("SELECT 1 FROM faturamentos WHERE os_id=?", (order_id,)).fetchone():
                raise EstadoInvalidoError("Esta OS já foi faturada.")
            c.execute(
                "INSERT INTO faturamentos(os_id,valor_centavos,usuario_id) VALUES (?,?,?)",
                (order_id, order.total, actor_id),
            )
            self._audit(c, order_id, actor_id, "Faturamento registrado")

    def pay(self, actor_id: int, order_id: int, amount: int, method: str):
        v.integer(amount, "Valor do pagamento")
        if method not in {"Pix", "Dinheiro", "Cartão", "Débito", "Sem cobrança"}:
            raise ValidacaoError("Selecione uma forma de pagamento válida.")
        with self.database.transaction(write=True) as c:
            self._access(c, actor_id, order_id, "administrar")
            invoice = c.execute("SELECT * FROM faturamentos WHERE os_id=?", (order_id,)).fetchone()
            if invoice is None:
                raise EstadoInvalidoError("Fature a OS antes de registrar o pagamento.")
            if c.execute(
                "SELECT 1 FROM pagamentos WHERE faturamento_id=?", (invoice["id"],)
            ).fetchone():
                raise EstadoInvalidoError("O pagamento desta OS já foi registrado.")
            if amount != invoice["valor_centavos"]:
                raise ValidacaoError(
                    "Nesta versão, o pagamento deve corresponder ao valor integral da fatura."
                )
            if (amount == 0) != (method == "Sem cobrança"):
                raise ValidacaoError("Use 'Sem cobrança' somente para faturas de valor zero.")
            c.execute(
                "INSERT INTO pagamentos(faturamento_id,valor_centavos,forma,usuario_id) VALUES (?,?,?,?)",
                (invoice["id"], amount, method, actor_id),
            )
            self._audit(c, order_id, actor_id, "Pagamento registrado")

    def deliver(self, actor_id: int, order_id: int):
        with self.database.transaction(write=True) as c:
            order = self._access(c, actor_id, order_id, "administrar")
            row = Repository(c).get("ordens_servico", order_id)
            if row["data_entrega"]:
                raise EstadoInvalidoError("A entrega desta OS já foi registrada.")
            paid = c.execute(
                "SELECT 1 FROM pagamentos p JOIN faturamentos f ON f.id=p.faturamento_id WHERE f.os_id=?",
                (order_id,),
            ).fetchone()
            if order.status != StatusOS.CONCLUIDA or not paid:
                raise EstadoInvalidoError(
                    "Conclua, fature e registre o pagamento antes da entrega."
                )
            c.execute(
                "UPDATE ordens_servico SET data_entrega=strftime('%Y-%m-%dT%H:%M:%SZ','now') WHERE id=?",
                (order_id,),
            )
            self._audit(c, order_id, actor_id, "Veículo entregue")

    def list(self, actor_id: int, search="", status="", history=False) -> list[dict]:
        with self.database.transaction() as c:
            actor = self.actor(c, actor_id)
            where, params = [], []
            if actor.perfil == Perfil.MECANICO:
                if history:
                    where.append(
                        "o.veiculo_id IN (SELECT veiculo_id FROM ordens_servico WHERE mecanico_id=?)"
                    )
                else:
                    where.append("o.mecanico_id=?")
                params.append(actor_id)
            if search.strip():
                where.append("(cl.nome LIKE ? OR v.placa LIKE ? OR cl.cpf LIKE ?)")
                term = "%" + search.strip() + "%"
                params.extend([term, "%" + search.strip().upper().replace("-", "") + "%", term])
            if status:
                where.append("o.status=?")
                params.append(status)
            suffix = " WHERE " + " AND ".join(where) if where else ""
            rows = c.execute(
                """SELECT o.id,cl.nome AS cliente,v.placa,v.modelo,
                u.nome AS mecanico,o.status,o.data_abertura,o.data_conclusao,o.data_entrega,
                COALESCE((SELECT SUM(quantidade*valor_centavos) FROM itens_peca_os WHERE os_id=o.id),0)
                + COALESCE((SELECT SUM(valor_centavos) FROM itens_servico_os WHERE os_id=o.id),0) AS total_centavos
                FROM ordens_servico o JOIN clientes cl ON cl.id=o.cliente_id
                JOIN veiculos v ON v.id=o.veiculo_id LEFT JOIN usuarios u ON u.id=o.mecanico_id"""
                + suffix
                + " ORDER BY o.id DESC",
                params,
            )
            return [dict(r) for r in rows]

    def detail(self, actor_id: int, order_id: int, history=False) -> dict:
        with self.database.transaction() as c:
            actor = self.actor(c, actor_id)
            repo = Repository(c)
            order = repo.order(order_id)
            allowed = actor.permite("visualizar", order.mecanico_id)
            if history and actor.perfil == Perfil.MECANICO:
                allowed = (
                    c.execute(
                        "SELECT 1 FROM ordens_servico WHERE veiculo_id=? AND mecanico_id=?",
                        (order.veiculo_id, actor_id),
                    ).fetchone()
                    is not None
                )
            if not allowed:
                raise PermissaoNegadaError("Você não possui acesso ao histórico deste veículo.")
            result = {
                "order": order,
                "metadata": dict(repo.get("ordens_servico", order_id)),
                "cliente": repo.get("clientes", order.cliente_id)["nome"],
                "veiculo": dict(repo.get("veiculos", order.veiculo_id)),
                "historico": [
                    dict(r)
                    for r in c.execute(
                        "SELECT h.*,u.nome AS responsavel FROM historico_status_os h JOIN usuarios u ON u.id=h.usuario_id WHERE os_id=? ORDER BY h.id",
                        (order_id,),
                    )
                ],
                "auditoria": [
                    dict(r)
                    for r in c.execute(
                        "SELECT a.*,u.nome AS responsavel FROM auditoria_os a JOIN usuarios u ON u.id=a.usuario_id WHERE os_id=? ORDER BY a.id DESC",
                        (order_id,),
                    )
                ],
            }
            # Dados financeiros só são carregados para administradores.
            result["fatura"] = result["pagamento"] = None
            if actor.perfil == Perfil.ADMIN:
                invoice = c.execute(
                    "SELECT * FROM faturamentos WHERE os_id=?", (order_id,)
                ).fetchone()
                result["fatura"] = dict(invoice) if invoice else None
                payment = c.execute(
                    "SELECT p.* FROM pagamentos p JOIN faturamentos f ON f.id=p.faturamento_id WHERE f.os_id=?",
                    (order_id,),
                ).fetchone()
                result["pagamento"] = dict(payment) if payment else None
            return result

    def export_pdf(self, actor_id: int, order_id: int, history=False) -> bytes:
        from oficina.infrastructure.order_pdf import render_order_pdf

        # A autorização é a mesma da consulta, inclusive para o histórico do mecânico.
        detail = self.detail(actor_id, order_id, history=history)
        return render_order_pdf(detail)
