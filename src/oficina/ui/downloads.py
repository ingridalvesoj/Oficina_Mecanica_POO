"""Entrega ao navegador do PDF já gerado pela ação de aprovação."""

from base64 import b64encode
from pathlib import Path
from uuid import uuid4

import streamlit as st
import streamlit.components.v2 as components

_download = components.component(
    "oficina_automatic_download",
    html='<span hidden aria-hidden="true"></span>',
    js=Path(__file__).with_suffix(".js").read_text(encoding="utf-8"),
)


def queue_pdf_download(pdf: bytes, filename: str):
    st.session_state["pending_pdf_download"] = {
        "token": uuid4().hex,
        "content": b64encode(pdf).decode("ascii"),
        "filename": filename,
    }


def show_pending_download():
    pending = st.session_state.pop("pending_pdf_download", None)
    _download(data=pending or {}, key="automatic_pdf_download")
