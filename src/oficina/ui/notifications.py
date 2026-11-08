"""Confirmações transitórias: fecham na próxima interação ou após alguns segundos."""

import streamlit as st
import streamlit.components.v2 as components

_popup = components.component(
    "oficina_confirmation",
    html='<aside role="status" aria-live="polite" hidden><span></span><button aria-label="Fechar confirmação">×</button></aside>',
    css="""
        aside {position:fixed;top:65px;right:20px;z-index:999999;
          background:#fff8fc;color:#672243;border:1px solid #e6adc6;
          border-left:5px solid #b52d70;border-radius:12px;padding:16px 42px 16px 18px;
          box-shadow:0 6px 24px #84234e22;font:14px/1.5 sans-serif;
          max-width:min(420px, calc(100vw - 40px));box-sizing:border-box;}
        aside[hidden] {display:none;}
        button {position:absolute;right:10px;top:8px;border:0;background:transparent;
          color:#84234e;cursor:pointer;font-size:22px;}
    """,
    js="""
        export default function({parentElement, data}) {
          const popup = parentElement.querySelector('aside');
          popup.querySelector('span').textContent = data.message || '';
          popup.hidden = !data.message;
          if (!data.message) return;
          const dismiss = () => { popup.hidden = true; };
          document.addEventListener('pointerdown', dismiss, true);
          document.addEventListener('keydown', dismiss, true);
          const timer = setTimeout(dismiss, 5000);
          return () => {
            clearTimeout(timer);
            document.removeEventListener('pointerdown', dismiss, true);
            document.removeEventListener('keydown', dismiss, true);
          };
        }
    """,
)


def show_confirmation():
    message = st.session_state.pop("flash", "")
    _popup(data={"message": message}, key="confirmation_popup")
