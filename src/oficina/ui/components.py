import logging
from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from oficina.domain.exceptions import OficinaError


def money(value: int) -> str:
    whole, fraction = divmod(value, 100)
    grouped = f"{whole:,}".replace(",", ".")
    return f"R$ {grouped},{fraction:02d}"


def date_display(value):
    if not value:
        return "—"
    return (
        datetime.fromisoformat(value.replace("Z", "+00:00"))
        .astimezone(ZoneInfo("America/Sao_Paulo"))
        .strftime("%d/%m/%Y %H:%M")
    )


def execute(action: Callable, success: str):
    try:
        result = action()
    except OficinaError as exc:
        st.error(str(exc))
        return None
    except Exception:
        logging.getLogger(__name__).exception("Falha inesperada na ação da interface")
        st.error("Não foi possível executar a operação. Tente novamente ou consulte o responsável.")
        return None
    st.session_state["flash"] = success
    st.session_state["revision"] = st.session_state.get("revision", 0) + 1
    if isinstance(result, int) and not isinstance(result, bool):
        st.session_state["last_created"] = result
    st.rerun()


def table(rows: list[dict], empty="Nenhum registro encontrado."):
    if not rows:
        st.info(empty)
        return
    display = []
    labels = {
        "id": "Código",
        "os_id": "OS",
        "cliente_id": "Cliente (código)",
        "veiculo_id": "Veículo (código)",
        "mecanico_id": "Mecânico (código)",
        "nome": "Nome",
        "descricao": "Descrição",
        "situacao": "Situação",
        "status": "Situação",
        "ativo": "Cadastro",
        "cpf": "CPF",
        "email": "E-mail",
        "valor_centavos": "Valor",
        "total_centavos": "Total",
        "subtotal_centavos": "Subtotal",
        "estoque": "Saldo físico",
        "disponivel": "Disponível",
        "mecanico": "Mecânico",
        "responsavel": "Responsável",
        "acao": "Ação",
        "data_abertura": "Abertura",
        "data_conclusao": "Conclusão",
        "data_entrega": "Entrega",
        "anterior": "Situação anterior",
        "novo": "Nova situação",
        "data": "Data e hora",
    }
    for row in rows:
        converted = {}
        for key, value in row.items():
            if key == "usuario_id" and "responsavel" in row:
                continue
            label = labels.get(key, key.replace("_", " ").capitalize())
            if key.endswith("centavos"):
                converted[label] = money(value)
            elif key.startswith("data") and isinstance(value, str):
                converted[label] = date_display(value)
            elif key == "ativo":
                converted[label] = "Ativo" if value else "Inativo"
            else:
                converted[label] = value
        display.append(converted)
    st.dataframe(display, hide_index=True, use_container_width=True)


def select_record(label, records, label_field="nome", key=None, optional=False, current=None):
    mapping = {r["id"]: r for r in records}
    options = ([None] if optional else []) + list(mapping)
    if not options:
        st.info(f"Nenhuma opção disponível para {label.lower()}.")
        return None

    def format_option(record_id):
        return "Não atribuído" if record_id is None else str(mapping[record_id][label_field])

    index = options.index(current) if current in options else 0
    return st.selectbox(label, options, index=index, format_func=format_option, key=key)
