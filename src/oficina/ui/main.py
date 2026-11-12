import logging

import streamlit as st

from oficina.application.auth_service import AuthService
from oficina.application.cadastro_service import CadastroService
from oficina.application.estoque_service import EstoqueService
from oficina.application.ordem_service import OrdemService
from oficina.config import LOGO_PATH, ROOT, database_path
from oficina.domain.enums import Perfil, StatusOS
from oficina.domain.exceptions import OficinaError
from oficina.infrastructure.database import Database

from .catalogs import render_catalog
from .components import execute, table
from .downloads import show_pending_download
from .notifications import show_confirmation
from .orders import render_orders


def render_login(auth):
    st.image(str(LOGO_PATH), width=260)
    #st.title("Oficina · Gestão de serviços")
    st.caption("Clientes, veículos e ordens de serviço em um só lugar.")
    if not auth.has_users():
        st.info("Primeiro acesso: crie o administrador da oficina. Não há senha padrão.")
        with st.form("bootstrap", enter_to_submit=False):
            name = st.text_input("Nome do administrador *")
            login = st.text_input("Login *")
            password = st.text_input(
                "Senha *",
                type="password",
                help="Mínimo de 8 caracteres, uma letra maiúscula, uma minúscula e um caractere especial.",
            )
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
    with st.form("login", enter_to_submit=False):
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
    st.set_page_config(page_title="Oficina · Gestão de serviços", page_icon=LOGO_PATH, layout="wide")
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
        [data-testid="stSidebar"] {border-right: 1px solid #edc9d9;}
        [data-testid="stMetric"] {background:#fff0f6;border:1px solid #edc9d9;border-radius:16px;padding:18px;}
        [data-testid="stMetricValue"] {font-size:1.35rem;}
        [data-testid="stMetricValue"] > div {white-space:normal;}
        h1, h2, h3 {color:#84234e;}
        [data-testid="stButton"] button,
        [data-testid="stFormSubmitButton"] button,
        [data-testid="stDownloadButton"] button {
            background-color:#b52d70 !important;color:white !important;border-color:#b52d70 !important;
        }
        [data-testid="stButton"] button:hover,
        [data-testid="stFormSubmitButton"] button:hover,
        [data-testid="stDownloadButton"] button:hover {filter:brightness(.92);}
        [data-testid="stButton"] button:disabled,
        [data-testid="stFormSubmitButton"] button:disabled,
        [data-testid="stDownloadButton"] button:disabled {opacity:.45;}
        button:focus-visible {outline:3px solid #84234e;outline-offset:3px;}
        .block-container {padding-top:2rem;max-width:1450px;}
        </style>""",
        unsafe_allow_html=True,
    )
    show_confirmation()
    show_pending_download()
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
            st.image(str(LOGO_PATH), width=240)
            st.write(f"Usuário: {actor.nome}")
            st.caption(f"Perfil: {str(actor.perfil)}")
            pages = (
                [
                    "Início",
                    "Clientes",
                    "Veículos",
                    "Usuários",
                    "Serviços",
                    "Peças e estoque",
                    "Ordens de serviço",
                    "Histórico",
                ]
                if actor.perfil == Perfil.ADMIN
                else ["Início", "Ordens de serviço", "Histórico"]
            )
            page = st.radio("Navegação", pages, key="navigation")
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
        elif page in {"Ordens de serviço", "Histórico"}:
            render_orders(actor, catalog, orders, history=page == "Histórico")
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
