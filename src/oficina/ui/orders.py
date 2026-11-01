import streamlit as st

from oficina.domain.enums import Perfil, StatusOS, StatusServico
from oficina.domain.validators import cents

from .components import date_display, execute, money, select_record, table


def render_orders(actor, catalog, orders, history=False, finance=False):
    st.title(
        "Histórico de atendimentos"
        if history
        else "Faturamento e entrega"
        if finance
        else "Ordens de serviço"
    )
    st.caption("Acompanhe cada atendimento, do orçamento à entrega do veículo.")
    revision = st.session_state.get("revision", 0)
    admin = actor.perfil == Perfil.ADMIN
    if admin and not history and not finance:
        with st.expander("Abrir nova ordem de serviço"):
            clients = catalog.list(actor.id, "clientes", active_only=True)
            client_id = select_record("Cliente *", clients, key="new_os_client")
            vehicles = [
                r
                for r in catalog.list(actor.id, "veiculos", active_only=True)
                if r["cliente_id"] == client_id
            ]
            mechanics = [
                r
                for r in catalog.list(actor.id, "usuarios", active_only=True)
                if r["perfil"] == Perfil.MECANICO
            ]
            with st.form(f"new_order_{revision}"):
                vehicle_id = select_record("Veículo *", vehicles, "placa")
                mechanic_id = select_record("Mecânico responsável", mechanics, optional=True)
                problem = st.text_area("Problema relatado *")
                submitted = st.form_submit_button(
                    "Abrir OS", type="primary", disabled=client_id is None or vehicle_id is None
                )
            if submitted:
                execute(
                    lambda: orders.create(actor.id, client_id, vehicle_id, problem, mechanic_id),
                    "Ordem de serviço aberta.",
                )
    c1, c2 = st.columns([2, 1])
    search = c1.text_input("Pesquisar por cliente, CPF ou placa")
    status = c2.selectbox("Situação", [""] + list(StatusOS), format_func=lambda x: x or "Todas")
    rows = orders.list(actor.id, search, status, history=history)
    if finance:
        rows = [r for r in rows if r["status"] == StatusOS.CONCLUIDA]
    table(rows)
    if not rows:
        return
    chosen = select_record(
        "Abrir detalhes da OS",
        [{"id": r["id"], "nome": f"{r['placa']} · {r['cliente']} · {r['status']}"} for r in rows],
        key=f"order_pick_{history}_{finance}",
    )
    if chosen is not None:
        render_detail(actor, catalog, orders, chosen, history)


def render_detail(actor, catalog, orders, order_id, read_only=False):
    detail = orders.detail(actor.id, order_id, history=read_only)
    order = detail["order"]
    meta = detail["metadata"]
    admin = actor.perfil == Perfil.ADMIN
    revision = st.session_state.get("revision", 0)
    key = f"os_{order_id}_{revision}"
    st.divider()
    st.subheader(f"OS #{order_id} · {detail['veiculo']['placa']}")
    c1, c2, c3 = st.columns(3)
    c1.metric("Situação", str(order.status))
    c2.metric("Valor total", money(order.total))
    c3.metric(
        "Serviços finalizados",
        f"{sum(s.status == StatusServico.FINALIZADO for s in order.servicos)}/{len(order.servicos)}",
    )
    st.write(f"**Cliente:** {detail['cliente']}")
    st.write(f"**Abertura:** {date_display(meta['data_abertura'])}")
    st.write("**Problema relatado**")
    st.text(order.problema)
    if meta["data_entrega"]:
        st.success(f"Veículo entregue em {date_display(meta['data_entrega'])}.")
    tab_items, tab_flow, tab_finance, tab_history = st.tabs(
        ["Peças e serviços", "Andamento", "Faturamento", "Histórico e solicitações"]
    )
    editable = order.status not in {StatusOS.CONCLUIDA, StatusOS.CANCELADA} and not read_only
    with tab_items:
        st.markdown("**Peças**")
        table(
            [
                {
                    "id": p.id,
                    "descricao": p.descricao,
                    "quantidade": p.quantidade,
                    "valor_centavos": p.valor_centavos,
                    "subtotal_centavos": p.subtotal,
                    "situacao": "Consumida"
                    if p.consumido
                    else "Reserva liberada"
                    if order.status == StatusOS.CANCELADA
                    else "Reservada",
                }
                for p in order.pecas
            ],
            "Nenhuma peça adicionada.",
        )
        st.markdown("**Serviços**")
        table(
            [
                {
                    "id": s.id,
                    "descricao": s.descricao,
                    "valor_centavos": s.valor_centavos,
                    "situacao": str(s.status),
                }
                for s in order.servicos
            ],
            "Nenhum serviço adicionado.",
        )
        if admin and editable:
            parts = catalog.list(actor.id, "pecas", active_only=True)
            services = catalog.list(actor.id, "servicos", active_only=True)
            with st.form(f"add_part_{key}"):
                part_id = select_record("Peça", parts, "descricao")
                quantity = st.number_input("Quantidade", 1, 1_000_000, 1, step=1)
                reason = st.text_input(
                    "Justificativa (obrigatória durante a execução)", key=f"part_reason_{key}"
                )
                add_part = st.form_submit_button("Adicionar peça", disabled=part_id is None)
            if add_part:
                execute(
                    lambda: orders.add_part(actor.id, order_id, part_id, quantity, reason),
                    "Peça adicionada à OS.",
                )
            with st.form(f"add_service_{key}"):
                service_id = select_record("Serviço", services, "descricao")
                service_reason = st.text_input(
                    "Justificativa (obrigatória durante a execução)", key=f"service_reason_{key}"
                )
                add_service = st.form_submit_button(
                    "Adicionar serviço", disabled=service_id is None
                )
            if add_service:
                execute(
                    lambda: orders.add_service(actor.id, order_id, service_id, service_reason),
                    "Serviço adicionado à OS.",
                )
            items = [("peca", p.id, p.descricao) for p in order.pecas if not p.consumido] + [
                ("servico", s.id, s.descricao)
                for s in order.servicos
                if s.status == StatusServico.PENDENTE
            ]
            if items:
                with st.form(f"remove_{key}"):
                    item = st.selectbox(
                        "Item para remover", items, format_func=lambda i: f"{i[0]} #{i[1]} · {i[2]}"
                    )
                    removal_reason = st.text_input("Justificativa da remoção")
                    confirm = st.checkbox("Confirmo a remoção do item")
                    remove = st.form_submit_button("Remover item")
                if remove:
                    if not confirm:
                        st.error("Confirme a remoção do item.")
                    else:
                        execute(
                            lambda: orders.remove_item(
                                actor.id, order_id, item[0], item[1], removal_reason
                            ),
                            "Item removido.",
                        )
            st.caption(
                "Alterar itens antes da execução devolve orçamentos pendentes ou aprovados para nova revisão. Peças consumidas e serviços iniciados não podem ser removidos."
            )
    with tab_flow:
        if admin and editable:
            mechanics = [
                r
                for r in catalog.list(actor.id, "usuarios", active_only=True)
                if r["perfil"] == Perfil.MECANICO
            ]
            with st.form(f"general_{key}"):
                problem = st.text_area("Problema relatado", order.problema)
                mechanic_id = select_record(
                    "Mecânico responsável", mechanics, optional=True, current=order.mecanico_id
                )
                save = st.form_submit_button("Salvar dados gerais")
            if save:
                execute(
                    lambda: orders.edit(actor.id, order_id, problem, mechanic_id),
                    "Dados da OS atualizados.",
                )
        if editable:
            next_actions = {
                StatusOS.ABERTA: [("Iniciar orçamento", StatusOS.ORCAMENTO)],
                StatusOS.ORCAMENTO: [("Enviar para aprovação", StatusOS.AGUARDANDO)],
                StatusOS.AGUARDANDO: [("Aprovar orçamento", StatusOS.APROVADA)],
                StatusOS.APROVADA: [("Iniciar execução", StatusOS.EXECUCAO)],
                StatusOS.EXECUCAO: [("Concluir OS", StatusOS.CONCLUIDA)],
            }
            for label, target in next_actions.get(order.status, []):
                if admin or target in {StatusOS.EXECUCAO, StatusOS.CONCLUIDA}:
                    if st.button(label, type="primary", key=f"transition_{target}_{key}"):
                        execute(
                            lambda: orders.transition(actor.id, order_id, target),
                            "Situação da OS atualizada.",
                        )
            if order.status == StatusOS.EXECUCAO:
                for service in order.servicos:
                    if service.status == StatusServico.FINALIZADO:
                        continue
                    target = (
                        StatusServico.EXECUCAO
                        if service.status == StatusServico.PENDENTE
                        else StatusServico.FINALIZADO
                    )
                    label = "Iniciar" if target == StatusServico.EXECUCAO else "Finalizar"
                    if st.button(
                        f"{label} serviço #{service.id} · {service.descricao}",
                        key=f"service_{service.id}_{key}",
                    ):
                        execute(
                            lambda: orders.update_service(actor.id, order_id, service.id, target),
                            "Andamento do serviço atualizado.",
                        )
            if admin and order.status != StatusOS.EXECUCAO:
                with st.expander("Cancelar ordem de serviço"):
                    with st.form(f"cancel_{key}"):
                        reason = st.text_input("Motivo do cancelamento *")
                        confirmed = st.checkbox(
                            "Confirmo o cancelamento e a liberação das reservas"
                        )
                        submitted = st.form_submit_button("Cancelar OS")
                    if submitted:
                        if not confirmed:
                            st.error("Confirme o cancelamento.")
                        else:
                            execute(
                                lambda: orders.transition(
                                    actor.id, order_id, StatusOS.CANCELADA, reason
                                ),
                                "OS cancelada. Reservas liberadas.",
                            )
        else:
            st.info("Consulta do atendimento. Não há ações de andamento disponíveis nesta tela.")
    with tab_finance:
        if not admin:
            st.info("Faturamento disponível apenas para administradores.")
        else:
            render_finance(actor, orders, detail, read_only, key)
    with tab_history:
        st.markdown("**Mudanças de situação**")
        table(detail["historico"])
        st.markdown("**Ações e solicitações**")
        table(detail["auditoria"], "Nenhuma ação adicional registrada.")
        if editable and not admin:
            with st.form(f"request_{key}"):
                request = st.text_area("Solicitar inclusão ou alteração de peças e serviços")
                submitted = st.form_submit_button("Registrar solicitação")
            if submitted:
                execute(
                    lambda: orders.request_change(actor.id, order_id, request),
                    "Solicitação registrada para análise do administrador.",
                )


def render_finance(actor, orders, detail, read_only, key):
    order = detail["order"]
    invoice, payment = detail["fatura"], detail["pagamento"]
    if invoice:
        st.success(
            f"Fatura #{invoice['id']} · {money(invoice['valor_centavos'])} · {date_display(invoice['data'])}"
        )
    else:
        st.info("Esta OS ainda não foi faturada.")
    if payment:
        st.success(f"Pagamento: {payment['forma']} · {money(payment['valor_centavos'])}")
    if read_only:
        return
    if order.status == StatusOS.CONCLUIDA and not invoice:
        if st.button("Faturar OS", type="primary", key=f"invoice_{key}"):
            execute(lambda: orders.invoice(actor.id, order.id), "Faturamento registrado.")
    if invoice and not payment:
        with st.form(f"payment_{key}"):
            total = invoice["valor_centavos"]
            raw_amount = st.text_input(
                "Valor integral recebido (R$)", f"{total // 100},{total % 100:02d}"
            )
            method = st.selectbox(
                "Forma de pagamento",
                ["Sem cobrança"] if total == 0 else ["Pix", "Dinheiro", "Cartão", "Transferência"],
            )
            confirmed = st.checkbox("Confirmo o recebimento do valor informado")
            submitted = st.form_submit_button("Registrar pagamento")
        if submitted:
            if not confirmed:
                st.error("Confirme o recebimento antes de registrar o pagamento.")
            else:
                execute(
                    lambda: orders.pay(actor.id, order.id, cents(raw_amount), method),
                    "Pagamento registrado.",
                )
    if payment and not detail["metadata"]["data_entrega"]:
        if st.button("Registrar entrega do veículo", key=f"deliver_{key}"):
            execute(lambda: orders.deliver(actor.id, order.id), "Entrega registrada.")
