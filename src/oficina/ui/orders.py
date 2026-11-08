import streamlit as st

from oficina.domain.enums import Perfil, StatusOS, StatusServico
from oficina.domain.exceptions import PermissaoNegadaError, RegistroNaoEncontradoError
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
    status = c2.selectbox(
        "Situação",
        [""] + [status for status in StatusOS if status != StatusOS.ABERTA],
        format_func=lambda x: x or "Todas",
    )
    rows = orders.list(actor.id, search, status, history=history)
    if finance:
        rows = [r for r in rows if r["status"] == StatusOS.CONCLUIDA]
    table(rows)
    selection_key = f"order_pick_{history}_{finance}"
    current = st.session_state.get(selection_key)
    options = [
        {"id": r["id"], "nome": f"{r['placa']} · {r['cliente']} · {r['status']}"} for r in rows
    ]
    if current is not None and current not in [r["id"] for r in rows]:
        try:
            selected = orders.detail(actor.id, current, history=history)
        except (PermissaoNegadaError, RegistroNaoEncontradoError):
            st.session_state.pop(selection_key, None)
        else:
            options.append(
                {
                    "id": current,
                    "nome": f"{selected['veiculo']['placa']} · {selected['cliente']} · {selected['order'].status} (fora do filtro)",
                }
            )
            st.caption("A OS selecionada permanece aberta, mesmo após sair do filtro atual.")
    if not options:
        return
    chosen = select_record(
        "Abrir detalhes da OS",
        options,
        key=selection_key,
    )
    if chosen is not None:
        render_detail(actor, catalog, orders, chosen, history)


def render_detail(actor, catalog, orders, order_id, read_only=False):
    detail = orders.detail(actor.id, order_id, history=read_only)
    order = detail["order"]
    meta = detail["metadata"]
    admin = actor.perfil == Perfil.ADMIN
    key = f"os_{order_id}"
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
        st.caption(f"Entrega registrada em {date_display(meta['data_entrega'])}.")
    st.download_button(
        "Baixar ordem de serviço em PDF",
        data=orders.export_pdf(actor.id, order_id, history=read_only),
        file_name=f"ordem-servico-{order_id}.pdf",
        mime="application/pdf",
        key=f"pdf_{key}",
        on_click="ignore",
    )
    proposal = orders.approval_pdf(actor.id, order_id, history=read_only)
    if proposal:
        st.download_button(
            f"Baixar PDF do último orçamento enviado (versão {proposal['versao']})",
            data=proposal["arquivo"],
            file_name=f"orcamento-os-{order_id}-v{proposal['versao']}.pdf",
            mime="application/pdf",
            key=f"proposal_{key}",
            on_click="ignore",
        )
    labels = ["Peças e serviços", "Andamento"]
    if admin:
        labels.append("Faturamento")
    labels.append("Histórico e solicitações")
    tabs = dict(zip(labels, st.tabs(labels, key=f"tabs_{key}", on_change="rerun")))
    tab_flow, tab_history = tabs["Andamento"], tabs["Histórico e solicitações"]
    editable = order.status not in {StatusOS.CONCLUIDA, StatusOS.CANCELADA} and not read_only
    with tabs["Peças e serviços"]:
        render_items(actor, catalog, orders, order, editable, key)
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
                StatusOS.ORCAMENTO: [("Enviar para aprovação do cliente", StatusOS.AGUARDANDO)],
                StatusOS.AGUARDANDO: [
                    ("Aprovar orçamento", StatusOS.APROVADA),
                    ("Voltar ao orçamento", StatusOS.ORCAMENTO),
                ],
                StatusOS.APROVADA: [("Iniciar execução", StatusOS.EXECUCAO)],
                StatusOS.EXECUCAO: [("Concluir OS", StatusOS.CONCLUIDA)],
            }
            for label, target in next_actions.get(order.status, []):
                if admin or target == StatusOS.EXECUCAO:
                    if st.button(label, type="primary", key=f"transition_{target}_{key}"):
                        execute(
                            lambda: orders.transition(actor.id, order_id, target),
                            "OS enviada para aprovação do cliente. PDF gerado e disponível para baixar."
                            if target == StatusOS.AGUARDANDO
                            else "Situação da OS atualizada.",
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
                        f"{label} serviço · {service.descricao}",
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
    if admin:
        with tabs["Faturamento"]:
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
        st.write(f"Fatura · {money(invoice['valor_centavos'])} · {date_display(invoice['data'])}")
    else:
        st.info("Esta OS ainda não foi faturada.")
    if payment:
        st.write(f"Pagamento: {payment['forma']} · {money(payment['valor_centavos'])}")
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
                ["Sem cobrança"] if total == 0 else ["Pix", "Dinheiro", "Cartão de Crédito", "Cartão de Débito"],
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


def render_items(actor, catalog, orders, order, editable, key):
    admin = actor.perfil == Perfil.ADMIN
    order_id = order.id
    st.subheader("Itens adicionados à ordem")
    rows = [
        {
            "tipo": "Peça",
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
    ] + [
        {
            "tipo": "Serviço",
            "descricao": s.descricao,
            "quantidade": 1,
            "valor_centavos": s.valor_centavos,
            "subtotal_centavos": s.valor_centavos,
            "situacao": str(s.status),
        }
        for s in order.servicos
    ]
    table(rows, "Nenhuma peça ou serviço adicionado à ordem.")
    if not editable or (not admin and order.status != StatusOS.ORCAMENTO):
        return
    removable = [("peca", p.id, p.descricao) for p in order.pecas if not p.consumido] + [
        ("servico", s.id, s.descricao) for s in order.servicos if s.status == StatusServico.PENDENTE
    ]
    if admin and removable:
        with st.expander("Remover um item adicionado"):
            with st.form(f"remove_{key}"):
                item = st.selectbox(
                    "Item para remover",
                    removable,
                    format_func=lambda i: f"{'Peça' if i[0] == 'peca' else 'Serviço'} · {i[2]}",
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
    st.subheader("Adicione os Itens à Ordem Serviço")
    available = orders.item_catalog(actor.id, order.id)
    parts, services = available["pecas"], available["servicos"]
    part_column, service_column = st.columns(2)
    with part_column:
        with st.form(f"add_part_{key}"):
            part_id = select_record("Peça", parts, "descricao")
            quantity = st.number_input("Quantidade", 1, 1_000_000, 1, step=1)
            reason = st.text_input("Justificativa", key=f"part_reason_{key}")
            add_part = st.form_submit_button("Adicionar peça", disabled=part_id is None)
        if add_part:
            execute(
                lambda: orders.add_part(actor.id, order_id, part_id, quantity, reason),
                "Peça adicionada à OS.",
            )
    with service_column:
        with st.form(f"add_service_{key}"):
            service_id = select_record("Serviço", services, "descricao")
            service_reason = st.text_input("Justificativa", key=f"service_reason_{key}")
            add_service = st.form_submit_button("Adicionar serviço", disabled=service_id is None)
        if add_service:
            execute(
                lambda: orders.add_service(actor.id, order_id, service_id, service_reason),
                "Serviço adicionado à OS.",
            )
    st.caption(
        "Alterar itens antes da execução exige nova aprovação do orçamento. Peças consumidas e serviços iniciados não podem ser removidos."
    )
