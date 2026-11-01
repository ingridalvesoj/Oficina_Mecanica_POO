import logging

import streamlit as st

from oficina.application.auth_service import AuthService
from oficina.application.cadastro_service import CadastroService
from oficina.application.estoque_service import EstoqueService
from oficina.application.ordem_service import OrdemService
from oficina.config import ROOT, database_path
from oficina.domain.enums import Perfil, StatusOS
from oficina.domain.exceptions import OficinaError
from oficina.infrastructure.database import Database

from .catalogs import render_catalog
from .components import execute, table
from .orders import render_orders


def render_login(auth):
    st.title("Oficina · Gestão de serviços")
    st.caption("Clientes, veículos e ordens de serviço em um só lugar.")
    if not auth.has_users():
        st.info("Primeiro acesso: crie o administrador da oficina. Não há senha padrão.")
        with st.form("bootstrap"):
            name = st.text_input("Nome do administrador *")
            login = st.text_input("Login *")
            password = st.text_input("Senha *", type="password", help="Entre 10 e 128 caracteres.")
            confirmation = st.text_input("Confirmar senha *", type="password")
            submitted = st.form_submit_button("Criar administrador", type="primary")
        if submitted:
            if password != confirmation:
                st.error("As senhas não coincidem.")
            else:
                execute(
                    lambda: auth.bootstrap(name, login, password),
                    "Administrador criado. Entre com suas credenciais.",
                )
        return
    with st.form("login"):
        login = st.text_input("Login")
        password = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar", type="primary")
    if submitted:
        try:
            user = auth.login(login, password)
        except OficinaError as exc:
            st.error(str(exc))
        else:
            st.session_state.clear()
            st.session_state["actor_id"] = user.id
            st.rerun()


def main():
    st.set_page_config(page_title="Oficina · Gestão de serviços", page_icon="🔧", layout="wide")
    log_path = ROOT / "logs"
    log_path.mkdir(exist_ok=True)
    logging.basicConfig(
        filename=log_path / "oficina.log",
        level=logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        encoding="utf-8",
    )
    st.markdown(
        """<style>
        [data-testid="stSidebar"] {border-right: 1px solid #24364a;}
        [data-testid="stMetric"] {border:1px solid #28435b;border-radius:12px;padding:18px;}
        .block-container {padding-top:2rem;max-width:1450px;}
        </style>""",
        unsafe_allow_html=True,
    )
    if "flash" in st.session_state:
        st.success(st.session_state.pop("flash"))
    try:
        database = Database(database_path())
        database.migrate()
        auth = AuthService(database)
        if "actor_id" not in st.session_state:
            render_login(auth)
            return
        try:
            actor = auth.current(st.session_state["actor_id"])
        except OficinaError:
            st.session_state.clear()
            st.warning("A sessão não está mais disponível. Entre novamente.")
            render_login(auth)
            return
        catalog, stock, orders = (
            CadastroService(database),
            EstoqueService(database),
            OrdemService(database),
        )
        with st.sidebar:
            st.title("🔧 Oficina")
            st.write(actor.nome)
            st.caption(str(actor.perfil))
            pages = ["Início", "Ordens de serviço", "Histórico"]
            if actor.perfil == Perfil.ADMIN:
                pages += [
                    "Clientes",
                    "Veículos",
                    "Peças e estoque",
                    "Serviços",
                    "Usuários",
                    "Faturamento",
                ]
            page = st.radio("Navegação", pages)
            st.divider()
            if st.button("Sair", use_container_width=True):
                st.session_state.clear()
                st.rerun()
        if page == "Início":
            st.title("Visão geral da oficina")
            st.caption("Acompanhe os atendimentos e avance as próximas etapas.")
            rows = orders.list(actor.id)
            cols = st.columns(4)
            for column, label, count in zip(
                cols,
                ["Atendimentos", "Aguardando aprovação", "Em execução", "Concluídas"],
                [
                    len(rows),
                    sum(r["status"] == StatusOS.AGUARDANDO for r in rows),
                    sum(r["status"] == StatusOS.EXECUCAO for r in rows),
                    sum(r["status"] == StatusOS.CONCLUIDA for r in rows),
                ],
            ):
                column.metric(label, count)
            st.subheader("Atendimentos recentes")
            table(
                rows[:10],
                "Nenhum atendimento registrado. Comece cadastrando um cliente e seu veículo.",
            )
            if actor.perfil == Perfil.ADMIN:
                st.info(
                    "Primeiros passos: cadastre clientes, veículos e mecânicos; depois serviços, peças e entradas de estoque. Abra a OS para iniciar o atendimento."
                )
        elif page in {"Ordens de serviço", "Histórico", "Faturamento"}:
            render_orders(
                actor, catalog, orders, history=page == "Histórico", finance=page == "Faturamento"
            )
        else:
            mapping = {
                "Clientes": "clientes",
                "Veículos": "veiculos",
                "Peças e estoque": "pecas",
                "Serviços": "servicos",
                "Usuários": "usuarios",
            }
            render_catalog(actor, catalog, stock, mapping[page])
    except OficinaError as exc:
        st.error(str(exc))
        if st.button("Tentar novamente"):
            st.rerun()
    except Exception:
        logging.getLogger(__name__).exception("Falha inesperada ao carregar a aplicação")
        st.error("Não foi possível carregar esta tela. Tente novamente ou consulte o responsável.")
