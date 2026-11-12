import ast
import base64
import json

import pytest
from conftest import create_order
from streamlit.testing.v1 import AppTest

from oficina.config import ROOT
from oficina.domain.enums import StatusOS


def element(items, label):
    return next(item for item in items if item.label == label)


def download_data(app):
    component = next(
        item
        for item in app.get("bidi_component")
        if item.proto.component_name == "oficina_automatic_download"
    )
    return json.loads(component.proto.json)


def order_app(system, monkeypatch):
    monkeypatch.setenv("OFICINA_DB", str(system["db"].path))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
    app.session_state["actor_id"] = system["admin"]
    app.run()
    element(app.radio, "Navegação").set_value("Ordens de serviço").run()
    return app


def test_every_form_explicitly_disables_enter_submission():
    forms = []
    for path in (ROOT / "src/oficina/ui").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if (
                    isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "st"
                    and node.func.attr == "form"
                ):
                    forms.append(node)
                    value = next(
                        (item.value for item in node.keywords if item.arg == "enter_to_submit"),
                        None,
                    )
                    assert isinstance(value, ast.Constant) and value.value is False, path
    assert len(forms) == 12


def test_form_batches_values_until_submit_button(system, monkeypatch):
    app = order_app(system, monkeypatch)
    element(app.radio, "Navegação").set_value("Serviços").run()
    before = len(system["catalog"].list(system["admin"], "servicos"))
    element(app.text_input, "Descrição *").input("Serviço salvo apenas pelo botão")
    element(app.text_input, "Valor (R$) *").input("20,00")
    assert len(system["catalog"].list(system["admin"], "servicos")) == before
    element(app.button, "Salvar cadastro").click().run()
    assert not app.error and not app.exception
    assert len(system["catalog"].list(system["admin"], "servicos")) == before + 1


def test_send_generates_and_queues_exact_stored_pdf_once(system, monkeypatch):
    s = system
    oid = create_order(s)
    s["orders"].add_service(s["admin"], oid, s["service"])
    app = order_app(s, monkeypatch)
    assert download_data(app) == {}
    element(app.button, "Enviar para aprovação do cliente").click().run()
    assert not app.error and not app.exception
    stored = s["orders"].approval_pdf(s["admin"], oid)
    payload = download_data(app)
    assert base64.b64decode(payload["content"]) == stored["arquivo"]
    assert payload["filename"] == f"orcamento-os-{oid}-v1.pdf"
    assert not any("último orçamento enviado" in item.label for item in app.get("download_button"))
    assert s["orders"].detail(s["admin"], oid)["order"].status == StatusOS.AGUARDANDO
    app.run()
    assert download_data(app) == {}
    element(app.button, "Voltar ao orçamento").click().run()
    element(app.button, "Enviar para aprovação do cliente").click().run()
    second = download_data(app)
    assert second["token"] != payload["token"]
    assert second["filename"] == f"orcamento-os-{oid}-v2.pdf"


def test_send_failure_does_not_start_download(system, monkeypatch):
    s = system
    oid = create_order(s)  # Sem serviços: envio inválido.
    app = order_app(s, monkeypatch)
    element(app.button, "Enviar para aprovação do cliente").click().run()
    assert app.error and not app.exception
    assert download_data(app) == {}
    assert s["orders"].detail(s["admin"], oid)["order"].status == StatusOS.ORCAMENTO
    assert s["orders"].approval_pdf(s["admin"], oid) is None


def test_pdf_write_failure_never_returns_a_download(system):
    from oficina.domain.exceptions import ValidacaoError

    s = system
    oid = create_order(s)
    s["orders"].add_service(s["admin"], oid, s["service"])
    with s["db"].transaction(write=True) as connection:
        connection.execute("""CREATE TRIGGER reject_pdf BEFORE INSERT ON orcamentos_pdf
            BEGIN SELECT RAISE(ABORT, 'PDF storage failure'); END""")
    with pytest.raises(ValidacaoError):
        s["orders"].transition(s["admin"], oid, StatusOS.AGUARDANDO)
    assert s["orders"].detail(s["admin"], oid)["order"].status == StatusOS.ORCAMENTO
    assert s["orders"].approval_pdf(s["admin"], oid) is None
