from datetime import date

import streamlit as st

from oficina.domain.enums import Perfil
from oficina.domain.validators import cents

from .components import execute, select_record, table

LABELS = {
    "clientes": "Clientes",
    "veiculos": "Veículos",
    "usuarios": "Usuários",
    "pecas": "Peças",
    "servicos": "Serviços",
}


def render_catalog(actor, catalog, stock, name):
    st.title(LABELS[name])
    st.caption("Cadastre, consulte e mantenha os registros da oficina.")
    records = catalog.list(actor.id, name)
    search = st.text_input("Pesquisar cadastro", key=f"search_{name}")
    filtered = [
        r for r in records if search.casefold() in " ".join(str(x) for x in r.values()).casefold()
    ]
    table(filtered)
    label_field = (
        "placa" if name == "veiculos" else "descricao" if name in {"pecas", "servicos"} else "nome"
    )
    revision = st.session_state.get("revision", 0)
    options = [None] + [r["id"] for r in filtered]
    mapping = {r["id"]: r for r in records}
    selected = st.selectbox(
        "Cadastro para editar",
        options,
        format_func=lambda x: "Novo cadastro" if x is None else f"#{x} · {mapping[x][label_field]}",
        key=f"edit_{name}",
    )
    previous = mapping.get(selected, {})
    key = f"{name}_{selected}_{revision}"
    st.subheader("Novo cadastro" if selected is None else f"Editar cadastro #{selected}")
    data = {}
    with st.form(key):
        if name in {"clientes", "usuarios"}:
            data["nome"] = st.text_input("Nome *", previous.get("nome", ""))
        if name == "clientes":
            data["cpf"] = st.text_input("CPF *", previous.get("cpf", ""))
            data["telefone"] = st.text_input("Telefone", previous.get("telefone", ""))
            data["email"] = st.text_input("E-mail", previous.get("email", ""))
        elif name == "usuarios":
            data["login"] = st.text_input("Login *", previous.get("login", ""))
            profiles = list(Perfil)
            data["perfil"] = st.selectbox(
                "Perfil *", profiles, index=profiles.index(previous.get("perfil", Perfil.MECANICO))
            )
            data["senha"] = st.text_input(
                "Senha *" if selected is None else "Nova senha (deixe vazio para manter)",
                type="password",
                help="Entre 10 e 128 caracteres.",
            )
        elif name == "veiculos":
            owners = [
                owner
                for owner in catalog.list(actor.id, "clientes")
                if owner["ativo"] or owner["id"] == previous.get("cliente_id")
            ]
            data["cliente_id"] = select_record(
                "Cliente proprietário *", owners, current=previous.get("cliente_id")
            )
            data["placa"] = st.text_input("Placa *", previous.get("placa", ""))
            data["marca"] = st.text_input("Marca *", previous.get("marca", ""))
            data["modelo"] = st.text_input("Modelo *", previous.get("modelo", ""))
            data["ano"] = st.number_input(
                "Ano *",
                1886,
                date.today().year + 1,
                value=previous.get("ano", date.today().year),
                step=1,
            )
        else:
            data["descricao"] = st.text_input("Descrição *", previous.get("descricao", ""))
            price = previous.get("valor_centavos", 0)
            raw_price = st.text_input("Valor (R$) *", f"{price // 100},{price % 100:02d}")
        st.caption("* Campo obrigatório")
        submitted = st.form_submit_button("Salvar cadastro", type="primary")
    if submitted:

        def save():
            if name in {"pecas", "servicos"}:
                data["valor_centavos"] = cents(raw_price)
            return catalog.save(actor.id, name, data, selected)

        execute(save, "Cadastro salvo com sucesso.")
    if selected is not None:
        with st.expander("Situação e exclusão"):
            confirmation = st.checkbox(
                "Confirmo a alteração de situação ou exclusão", key=f"confirm_{key}"
            )
            c1, c2 = st.columns(2)
            if c1.button(
                "Inativar" if previous["ativo"] else "Reativar",
                disabled=not confirmation,
                key=f"active_{key}",
            ):
                execute(
                    lambda: catalog.set_active(actor.id, name, selected, not previous["ativo"]),
                    "Situação atualizada.",
                )
            if c2.button(
                "Excluir cadastro sem vínculos", disabled=not confirmation, key=f"delete_{key}"
            ):
                execute(lambda: catalog.delete(actor.id, name, selected), "Cadastro excluído.")
            st.caption(
                "Cadastros com histórico devem ser inativados para preservar os atendimentos."
            )
    if name == "pecas":
        st.divider()
        st.subheader("Estoque")
        balances = stock.balances(actor.id)
        table(balances)
        with st.form(f"stock_{revision}"):
            part_id = select_record(
                "Peça para entrada", [p for p in balances if p["ativo"]], "descricao"
            )
            quantity = st.number_input("Quantidade de entrada", 1, 1_000_000, 1, step=1)
            reason = st.text_input(
                "Justificativa da entrada *", placeholder="Ex.: compra de reposição"
            )
            submitted = st.form_submit_button("Registrar entrada", disabled=part_id is None)
        if submitted:
            execute(
                lambda: stock.enter(actor.id, part_id, quantity, reason),
                "Entrada de estoque registrada.",
            )
        with st.expander("Movimentações de estoque"):
            table(stock.history(actor.id))
