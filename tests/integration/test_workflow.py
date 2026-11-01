from concurrent.futures import ThreadPoolExecutor

import pytest
from conftest import complete_order, create_order, execute_order

from oficina.application.ordem_service import OrdemService
from oficina.domain.enums import Perfil, StatusOS
from oficina.domain.exceptions import (
    CampoObrigatorioError,
    EstadoInvalidoError,
    EstoqueInsuficienteError,
    PermissaoNegadaError,
    RegistroNaoEncontradoError,
    ValidacaoError,
)
from oficina.infrastructure.database import Database


def test_full_workflow_and_recovery(system):
    s = system
    order_id = create_order(s)
    s["orders"].add_part(s["admin"], order_id, s["part"], 2)
    s["orders"].add_service(s["admin"], order_id, s["service"])
    assert s["stock"].balances(s["admin"])[0]["disponivel"] == 8
    assert s["stock"].balances(s["admin"])[0]["estoque"] == 10
    complete_order(s, order_id)
    s["orders"].invoice(s["admin"], order_id)
    s["orders"].pay(s["admin"], order_id, 15180, "Pix")
    s["orders"].deliver(s["admin"], order_id)
    recovered = OrdemService(Database(s["db"].path)).detail(s["admin"], order_id)
    assert recovered["order"].total == 15180
    assert recovered["order"].status == StatusOS.CONCLUIDA
    assert recovered["metadata"]["data_entrega"]
    assert recovered["pagamento"]["valor_centavos"] == 15180
    assert s["stock"].balances(s["admin"])[0]["estoque"] == 8
    assert len(s["orders"].list(s["admin"], "abc1d23")) == 1
    assert len(s["orders"].list(s["admin"], "Cliente teste")) == 1


def test_errors_and_required_relations(system):
    s = system
    with pytest.raises(CampoObrigatorioError):
        s["orders"].create(s["admin"], s["client"], s["vehicle"], "")
    with pytest.raises(RegistroNaoEncontradoError):
        s["orders"].detail(s["admin"], 9999)
    with pytest.raises(RegistroNaoEncontradoError):
        s["catalog"].save(s["admin"], "veiculos", {"cliente_id": 9999})
    with pytest.raises(ValidacaoError):
        s["catalog"].save(s["admin"], "clientes", {"nome": "Duplicado", "cpf": "52998224725"})
    order_id = create_order(s, mechanic=False)
    with pytest.raises(EstadoInvalidoError):
        s["orders"].transition(s["admin"], order_id, "Concluída")
    s["orders"].transition(s["admin"], order_id, "Em orçamento")
    with pytest.raises(EstadoInvalidoError):
        s["orders"].transition(s["admin"], order_id, "Aguardando aprovação")
    s["orders"].add_service(s["admin"], order_id, s["service"])
    s["orders"].transition(s["admin"], order_id, "Aguardando aprovação")
    s["orders"].transition(s["admin"], order_id, "Aprovada")
    with pytest.raises(EstadoInvalidoError):
        s["orders"].transition(s["admin"], order_id, "Em execução")


def test_approval_invalidation_and_rollback(system):
    s = system
    oid = create_order(s)
    s["orders"].add_service(s["admin"], oid, s["service"])
    for status in ("Em orçamento", "Aguardando aprovação", "Aprovada"):
        s["orders"].transition(s["admin"], oid, status)
    with pytest.raises(EstoqueInsuficienteError):
        s["orders"].add_part(s["admin"], oid, s["part"], 11)
    assert s["orders"].detail(s["admin"], oid)["order"].status == StatusOS.APROVADA
    s["orders"].add_part(s["admin"], oid, s["part"], 1)
    assert s["orders"].detail(s["admin"], oid)["order"].status == StatusOS.ORCAMENTO


def test_stock_concurrency(system):
    s = system
    orders = [create_order(s), create_order(s)]

    def reserve(oid):
        try:
            s["orders"].add_part(s["admin"], oid, s["part"], 7)
            return True
        except EstoqueInsuficienteError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(reserve, orders))
    assert sorted(results) == [False, True]
    assert s["stock"].balances(s["admin"])[0]["disponivel"] == 3


def test_reservation_removal_and_cancellation(system):
    s = system
    oid = create_order(s)
    item = s["orders"].add_part(s["admin"], oid, s["part"], 2)
    s["orders"].remove_item(s["admin"], oid, "peca", item)
    assert s["stock"].balances(s["admin"])[0]["disponivel"] == 10
    s["orders"].add_part(s["admin"], oid, s["part"], 3)
    s["orders"].transition(s["admin"], oid, "Cancelada", "Cliente desistiu")
    assert s["stock"].balances(s["admin"])[0]["disponivel"] == 10
    with pytest.raises(EstadoInvalidoError):
        s["orders"].add_part(s["admin"], oid, s["part"], 1)


def test_pending_services_and_execution_changes(system):
    s = system
    oid = create_order(s)
    service_id = s["orders"].add_service(s["admin"], oid, s["service"])
    execute_order(s, oid)
    with pytest.raises(EstadoInvalidoError):
        s["orders"].transition(s["mechanic"], oid, "Concluída")
    with pytest.raises(CampoObrigatorioError):
        s["orders"].add_part(s["admin"], oid, s["part"], 1)
    part = s["orders"].add_part(s["admin"], oid, s["part"], 1, "Necessidade identificada no reparo")
    assert s["stock"].balances(s["admin"])[0]["estoque"] == 9
    with pytest.raises(EstadoInvalidoError):
        s["orders"].remove_item(s["admin"], oid, "peca", part, "Remoção")
    with pytest.raises(EstadoInvalidoError):
        s["orders"].transition(s["admin"], oid, "Cancelada", "Teste")
    with pytest.raises(EstadoInvalidoError):
        s["orders"].update_service(s["mechanic"], oid, service_id, "Finalizado")


def test_permissions_and_historical_scope(system):
    s = system
    oid = create_order(s)
    unassigned = create_order(s, mechanic=False)
    with pytest.raises(PermissaoNegadaError):
        s["catalog"].list(s["mechanic"], "clientes")
    with pytest.raises(PermissaoNegadaError):
        s["orders"].add_part(s["mechanic"], oid, s["part"], 1)
    with pytest.raises(PermissaoNegadaError):
        s["orders"].detail(s["mechanic"], unassigned)
    # Histórico de veículo relacionado pode ser consultado, sem liberar ações.
    assert s["orders"].detail(s["mechanic"], unassigned, history=True)["order"].id == unassigned
    with pytest.raises(PermissaoNegadaError):
        s["orders"].transition(s["mechanic"], unassigned, "Em execução")
    other = s["catalog"].save(
        s["admin"],
        "usuarios",
        {
            "nome": "Outro",
            "login": "outro",
            "senha": "senha-teste-segura",
            "perfil": Perfil.MECANICO,
        },
    )
    with pytest.raises(PermissaoNegadaError):
        s["orders"].detail(other, oid, history=True)
    s["orders"].add_service(s["admin"], oid, s["service"])
    s["orders"].transition(s["admin"], oid, "Em orçamento")
    s["orders"].transition(s["admin"], oid, "Aguardando aprovação")
    with pytest.raises(PermissaoNegadaError):
        s["orders"].transition(s["mechanic"], oid, "Aprovada")
    with pytest.raises(PermissaoNegadaError):
        s["orders"].invoice(s["mechanic"], oid)


def test_price_snapshot_and_customer_history(system):
    s = system
    oid = create_order(s)
    s["orders"].add_service(s["admin"], oid, s["service"])
    s["orders"].add_part(s["admin"], oid, s["part"], 1)
    s["catalog"].save(
        s["admin"], "pecas", {"descricao": "Novo filtro", "valor_centavos": 99999}, s["part"]
    )
    s["catalog"].save(
        s["admin"], "servicos", {"descricao": "Novo serviço", "valor_centavos": 99999}, s["service"]
    )
    assert s["orders"].detail(s["admin"], oid)["order"].total == 12590
    with pytest.raises(EstadoInvalidoError):
        s["catalog"].delete(s["admin"], "clientes", s["client"])
    complete_order(s, oid)
    new_client = s["catalog"].save(
        s["admin"], "clientes", {"nome": "Novo proprietário", "cpf": "11144477735"}
    )
    s["catalog"].save(
        s["admin"],
        "veiculos",
        {
            "cliente_id": new_client,
            "placa": "ABC1D23",
            "marca": "Marca",
            "modelo": "Modelo",
            "ano": 2020,
        },
        s["vehicle"],
    )
    assert s["orders"].detail(s["admin"], oid)["order"].cliente_id == s["client"]
    s["catalog"].set_active(s["admin"], "clientes", s["client"], False)


def test_finance_idempotence_and_closed_order(system):
    s = system
    oid = create_order(s)
    s["orders"].add_service(s["admin"], oid, s["service"])
    with pytest.raises(EstadoInvalidoError):
        s["orders"].invoice(s["admin"], oid)
    complete_order(s, oid)
    with pytest.raises(EstadoInvalidoError):
        s["orders"].add_service(s["admin"], oid, s["service"])
    with pytest.raises(EstadoInvalidoError):
        s["orders"].deliver(s["admin"], oid)
    s["orders"].invoice(s["admin"], oid)
    with pytest.raises(EstadoInvalidoError):
        s["orders"].invoice(s["admin"], oid)
    with pytest.raises(ValidacaoError):
        s["orders"].pay(s["admin"], oid, 1, "Pix")
    s["orders"].pay(s["admin"], oid, 10000, "Pix")
    with pytest.raises(EstadoInvalidoError):
        s["orders"].pay(s["admin"], oid, 10000, "Pix")
    s["orders"].deliver(s["admin"], oid)
    with pytest.raises(EstadoInvalidoError):
        s["orders"].deliver(s["admin"], oid)


def test_authentication_and_last_admin(system):
    s = system
    assert s["auth"].login(" ADMIN ", "senha-teste-segura").id == s["admin"]
    with pytest.raises(PermissaoNegadaError):
        s["auth"].login("admin", "incorreta")
    with pytest.raises(PermissaoNegadaError):
        s["auth"].login("inexistente", "incorreta")
    with pytest.raises(EstadoInvalidoError):
        s["auth"].bootstrap("Outro", "outro", "senha-teste-segura")
    with pytest.raises(EstadoInvalidoError):
        s["catalog"].set_active(s["admin"], "usuarios", s["admin"], False)
    with pytest.raises(EstadoInvalidoError):
        s["catalog"].delete(s["admin"], "usuarios", s["admin"])
    s["catalog"].set_active(s["admin"], "usuarios", s["mechanic"], False)
    with pytest.raises(PermissaoNegadaError):
        s["auth"].login("mecanico", "senha-teste-segura")
    with pytest.raises(PermissaoNegadaError):
        s["orders"].list(s["mechanic"])
    with s["db"].transaction() as c:
        stored = c.execute("SELECT senha_hash FROM usuarios WHERE id=?", (s["admin"],)).fetchone()[
            0
        ]
        assert stored.startswith("pbkdf2_sha256$") and "senha-teste-segura" not in stored
