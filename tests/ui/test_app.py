import json

from conftest import create_order
from streamlit.testing.v1 import AppTest

from oficina.config import ROOT


def widget(elements, label):
    return next(element for element in elements if element.label == label)


def confirmation(app):
    component = next(
        element
        for element in app.get("bidi_component")
        if element.proto.component_name == "oficina_confirmation"
    )
    return json.loads(component.proto.json)["message"]


def app_for(system, monkeypatch, user="admin"):
    monkeypatch.setenv("OFICINA_DB", str(system["db"].path))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30)
    app.session_state["actor_id"] = system[user]
    app.run()
    assert not app.exception
    assert not app.error
    return app


def test_first_access_login_and_logout(tmp_path, monkeypatch):
    monkeypatch.setenv("OFICINA_DB", str(tmp_path / "ui.sqlite3"))
    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
    assert not app.exception
    widget(app.text_input, "Nome do administrador *").input("Administrador")
    widget(app.text_input, "Login *").input("admin")
    widget(app.text_input, "Senha *").input("senha-teste-segura")
    widget(app.text_input, "Confirmar senha *").input("senha-teste-segura")
    widget(app.button, "Criar administrador").click().run()
    assert not app.error
    assert confirmation(app) == "Administrador criado. Entre com suas credenciais."
    app.run()
    assert confirmation(app) == ""
    widget(app.text_input, "Login").input("admin")
    widget(app.text_input, "Senha").input("incorreta")
    widget(app.button, "Entrar").click().run()
    assert app.error
    widget(app.text_input, "Senha").input("senha-teste-segura")
    widget(app.button, "Entrar").click().run()
    assert not app.error
    assert app.title[1].value == "Visão geral da oficina" or any(
        t.value == "Visão geral da oficina" for t in app.title
    )
    widget(app.button, "Sair").click().run()
    assert any(button.label == "Entrar" for button in app.button)


def test_admin_navigation(system, monkeypatch):
    oid = create_order(system)
    system["orders"].add_service(system["admin"], oid, system["service"])
    app = app_for(system, monkeypatch)
    assert widget(app.radio, "Navegação").options == [
        "Início",
        "Clientes",
        "Veículos",
        "Usuários",
        "Serviços",
        "Peças e estoque",
        "Ordens de serviço",
        "Histórico",
    ]
    for page in [
        "Clientes",
        "Veículos",
        "Peças e estoque",
        "Serviços",
        "Usuários",
        "Ordens de serviço",
        "Histórico",
        "Início",
    ]:
        widget(app.radio, "Navegação").set_value(page).run()
        assert not app.exception, page
        assert not app.error, (page, [e.value for e in app.error])


def test_form_validation_preserves_data_and_saves(system, monkeypatch):
    app = app_for(system, monkeypatch)
    widget(app.radio, "Navegação").set_value("Clientes").run()
    widget(app.text_input, "Nome *").input("Cliente da interface")
    app.session_state["cpf_clientes_None_0"] = {"value": "123"}
    widget(app.button, "Salvar cadastro").click().run()
    assert app.error
    assert widget(app.text_input, "Nome *").value == "Cliente da interface"
    app.session_state["cpf_clientes_None_0"] = {"value": "111.444.777-35"}
    widget(app.button, "Salvar cadastro").click().run()
    assert not app.error
    assert len(system["catalog"].list(system["admin"], "clientes")) == 2
    app.run()  # Reexecução da tela não repete o cadastro.
    assert len(system["catalog"].list(system["admin"], "clientes")) == 2


def test_mechanic_navigation(system, monkeypatch):
    oid = create_order(system)
    system["orders"].add_service(system["admin"], oid, system["service"])
    app = app_for(system, monkeypatch, "mechanic")
    assert widget(app.radio, "Navegação").options == ["Início", "Ordens de serviço", "Histórico"]
    widget(app.radio, "Navegação").set_value("Ordens de serviço").run()
    assert not app.error
    assert "Faturamento" not in [tab.label for tab in app.tabs]
    assert not any(button.label == "Aprovar orçamento" for button in app.button)
    widget(app.text_area, "Solicitar inclusão ou alteração de peças e serviços").input(
        "Solicito inspeção adicional"
    )
    widget(app.button, "Registrar solicitação").click().run()
    assert not app.error
    assert (
        system["orders"].detail(system["admin"], oid)["auditoria"][0]["justificativa"]
        == "Solicito inspeção adicional"
    )


def test_full_order_through_interface(system, monkeypatch):
    app = app_for(system, monkeypatch)
    widget(app.radio, "Navegação").set_value("Ordens de serviço").run()
    widget(app.selectbox, "Mecânico responsável").set_value(system["mechanic"])
    widget(app.text_area, "Problema relatado *").input("Revisão via interface")
    widget(app.button, "Abrir OS").click().run()
    assert not app.error
    widget(app.button, "Adicionar peça").click().run()
    widget(app.button, "Adicionar serviço").click().run()
    oid = system["orders"].list(system["admin"])[0]["id"]
    app.session_state[f"tabs_os_{oid}"] = "Andamento"
    app.run()
    for label in [
        "Iniciar orçamento",
        "Enviar para aprovação",
        "Aprovar orçamento",
        "Iniciar execução",
    ]:
        widget(app.button, label).click().run()
        assert not app.error, [e.value for e in app.error]
        assert app.session_state[f"tabs_os_{oid}"] == "Andamento"
    next(b for b in app.button if b.label.startswith("Iniciar serviço ·")).click().run()
    next(b for b in app.button if b.label.startswith("Finalizar serviço ·")).click().run()
    widget(app.button, "Concluir OS").click().run()
    widget(app.button, "Faturar OS").click().run()
    assert "Débito" in widget(app.selectbox, "Forma de pagamento").options
    assert "Transferência" not in widget(app.selectbox, "Forma de pagamento").options
    widget(app.checkbox, "Confirmo o recebimento do valor informado").check()
    widget(app.button, "Registrar pagamento").click().run()
    widget(app.button, "Registrar entrega do veículo").click().run()
    assert not app.exception
    assert not app.error
    oid = system["orders"].list(system["admin"])[0]["id"]
    assert system["orders"].detail(system["admin"], oid)["metadata"]["data_entrega"]


def test_edit_vehicle_preserves_inactive_owner(system, monkeypatch):
    s = system
    s["catalog"].save(s["admin"], "clientes", {"nome": "Outro cliente", "cpf": "11144477735"})
    s["catalog"].set_active(s["admin"], "clientes", s["client"], False)
    app = app_for(s, monkeypatch)
    widget(app.radio, "Navegação").set_value("Veículos").run()
    assert widget(app.selectbox, "Ano *").value >= 1886
    widget(app.selectbox, "Cadastro para editar").set_value(s["vehicle"]).run()
    assert widget(app.selectbox, "Cliente proprietário *").value == s["client"]
    widget(app.text_input, "Modelo *").input("Modelo atualizado")
    widget(app.button, "Salvar cadastro").click().run()
    assert not app.error
    assert s["catalog"].get(s["admin"], "veiculos", s["vehicle"]).cliente_id == s["client"]


def test_order_stays_open_when_status_leaves_filter(system, monkeypatch):
    oid = create_order(system)
    app = app_for(system, monkeypatch)
    widget(app.radio, "Navegação").set_value("Ordens de serviço").run()
    widget(app.selectbox, "Situação").set_value("Aberta").run()
    app.session_state[f"tabs_os_{oid}"] = "Andamento"
    app.run()
    widget(app.button, "Iniciar orçamento").click().run()
    assert not app.error
    assert widget(app.selectbox, "Abrir detalhes da OS").value == oid
    assert app.session_state[f"tabs_os_{oid}"] == "Andamento"
    assert widget(app.button, "Enviar para aprovação")
