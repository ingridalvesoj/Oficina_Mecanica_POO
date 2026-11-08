from pathlib import Path

import streamlit as st
import streamlit.components.v2 as components

_masked = components.component(
    "oficina_masked_input",
    html='<label></label><input type="text" inputmode="numeric" />',
    css="""
        label {display:block;margin-bottom:8px;font:inherit;font-size:14px;color:#452a38;}
        input {box-sizing:border-box;width:100%;border:1px solid transparent;border-radius:8px;
          padding:10px 12px;background:#fbe7f0;color:#452a38;font:inherit;min-height:40px;}
        input:focus {outline:2px solid #b52d70;outline-offset:-2px;}
        input::placeholder {color:#896477;}
    """,
    js=Path(__file__).with_suffix(".js").read_text(encoding="utf-8"),
)


def masked_input(label: str, value: str = "", *, kind: str, key: str) -> str:
    current = st.session_state.get(key, {}).get("value", value)
    result = _masked(
        data={"label": label, "value": current, "kind": kind, "id": key},
        default={"value": current},
        key=key,
        on_value_change=lambda: None,
    )
    return result.value or ""
