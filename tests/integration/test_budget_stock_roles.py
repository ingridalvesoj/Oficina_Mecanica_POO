from concurrent.futures import ThreadPoolExecutor
from io import BytesIO

import pytest
from conftest import create_order, execute_order
from pypdf import PdfReader

from oficina.config import ROOT
from oficina.domain.enums import StatusOS
from oficina.domain.exceptions import (
    EstoqueInsuficienteError,
    PermissaoNegadaError,
    PersistenciaError,
    ValidacaoError,
)
from oficina.infrastructure.database import Database
from oficina.infrastructure.security import hash_password


@pytest.mark.parametrize("password", ["abcdefgh!", "ABCDEFGH!", "Abcdefgh", "Abcdef!", "1234567!"])
def test_password_requires_each_condition(password):
    with pytest.raises(ValidacaoError):
        hash_password(password)


def test_budget_rejection_reopens_mechanic_items_and_versions_pdf(system):
    s = system
    orders, admin, mechanic = s["orders"], s["admin"], s["mechanic"]
    oid = create_order(s)
    assert orders.detail(admin, oid)["order"].status == StatusOS.ORCAMENTO
    assert orders.item_catalog(mechanic, oid)["pecas"][0]["id"] == s["part"]
    orders.add_part(mechanic, oid, s["part"], 2)
    orders.add_service(mechanic, oid, s["service"])
    orders.transition(admin, oid, StatusOS.AGUARDANDO)
    proposal = orders.approval_pdf(mechanic, oid)
    assert proposal["versao"] == 1
    reader = PdfReader(BytesIO(proposal["arquivo"]))
    assert "Aguardando aprovação" in reader.pages[0].extract_text()
    assert "151,80" in "\n".join(p.extract_text() for p in reader.pages)
    assert reader.pages[0].images  # A logo também está incorporada ao documento.
    for action in (
        lambda: orders.add_part(mechanic, oid, s["part"], 1),
        lambda: orders.add_service(mechanic, oid, s["service"]),
        lambda: orders.item_catalog(mechanic, oid),
        lambda: orders.transition(mechanic, oid, StatusOS.ORCAMENTO),
    ):
        with pytest.raises(PermissaoNegadaError):
            action()
    orders.transition(admin, oid, StatusOS.ORCAMENTO, "Cliente pediu revisão")
    assert s["stock"].balances(admin)[0]["disponivel"] == 8
    orders.add_service(mechanic, oid, s["service"])
    orders.transition(admin, oid, StatusOS.AGUARDANDO)
    assert orders.approval_pdf(admin, oid)["versao"] == 2
    with s["db"].transaction() as c:
        rows = c.execute(
            "SELECT arquivo FROM orcamentos_pdf WHERE os_id=? ORDER BY versao", (oid,)
        ).fetchall()
        assert len(rows) == 2 and rows[0][0] == proposal["arquivo"]
    assert orders.detail(admin, oid)["historico"][-2]["justificativa"] == "Cliente pediu revisão"


def test_pdf_failure_rolls_back_send_and_history(system, monkeypatch):
    from oficina.infrastructure import order_pdf

    s = system
    oid = create_order(s)
    s["orders"].add_service(s["admin"], oid, s["service"])
    before = s["orders"].detail(s["admin"], oid)["historico"]

    def fail(_):
        raise OSError("Simulação de falha no gerador")

    monkeypatch.setattr(order_pdf, "render_order_pdf", fail)
    with pytest.raises(PersistenciaError, match="continua em orçamento"):
        s["orders"].transition(s["admin"], oid, StatusOS.AGUARDANDO)
    detail = s["orders"].detail(s["admin"], oid)
    assert detail["order"].status == StatusOS.ORCAMENTO
    assert detail["historico"] == before
    assert s["orders"].approval_pdf(s["admin"], oid) is None


def test_mechanic_finishes_service_but_not_order(system):
    s = system
    oid = create_order(s)
    item = s["orders"].add_service(s["mechanic"], oid, s["service"])
    with pytest.raises(PermissaoNegadaError):
        s["orders"].remove_item(s["mechanic"], oid, "servico", item)
    unassigned = create_order(s, mechanic=False)
    for action in (
        lambda: s["orders"].item_catalog(s["mechanic"], unassigned),
        lambda: s["orders"].add_service(s["mechanic"], unassigned, s["service"]),
        lambda: s["orders"].approval_pdf(s["mechanic"], unassigned),
    ):
        with pytest.raises(PermissaoNegadaError):
            action()
    execute_order(s, oid)
    s["orders"].update_service(s["mechanic"], oid, item, "Em execução")
    s["orders"].update_service(s["mechanic"], oid, item, "Finalizado")
    with pytest.raises(PermissaoNegadaError):
        s["orders"].transition(s["mechanic"], oid, StatusOS.CONCLUIDA)
    with pytest.raises(PermissaoNegadaError):
        s["orders"].add_service(s["mechanic"], oid, s["service"])
    s["orders"].transition(s["admin"], oid, StatusOS.CONCLUIDA)


def test_stock_exit_respects_reservations_and_records_actor(system):
    s = system
    oid = create_order(s)
    s["orders"].add_part(s["admin"], oid, s["part"], 7)
    before = s["stock"].history(s["admin"])
    with pytest.raises(EstoqueInsuficienteError):
        s["stock"].withdraw(s["admin"], s["part"], 4)
    assert s["stock"].history(s["admin"]) == before
    with pytest.raises(PermissaoNegadaError):
        s["stock"].withdraw(s["mechanic"], s["part"], 1)
    s["stock"].withdraw(s["admin"], s["part"], 3)
    balance = s["stock"].balances(s["admin"])[0]
    assert balance["estoque"] == 7 and balance["disponivel"] == 0
    movement = s["stock"].history(s["admin"])[0]
    assert (movement["tipo"], movement["quantidade"], movement["justificativa"]) == ("Saída", 3, "")
    assert movement["responsavel"] == "Administrador de teste"
    for quantity in (0, -1):
        with pytest.raises(ValidacaoError):
            s["stock"].withdraw(s["admin"], s["part"], quantity)
    s["orders"].add_service(s["admin"], oid, s["service"])
    execute_order(s, oid)
    assert s["stock"].balances(s["admin"])[0]["estoque"] == 0


def test_concurrent_stock_exits_cannot_overdraw(system):
    s = system

    def withdraw(_):
        try:
            s["stock"].withdraw(s["admin"], s["part"], 7)
            return True
        except EstoqueInsuficienteError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(withdraw, range(2))) == [False, True]
    assert s["stock"].balances(s["admin"])[0]["estoque"] == 3


def test_upgrade_preserves_stock_and_converts_open_orders(tmp_path):
    db = Database(tmp_path / "legacy.sqlite3")
    c = db.connect()
    c.executescript((ROOT / "migrations/001_initial.sql").read_text(encoding="utf-8"))
    c.executescript("""
        CREATE TABLE schema_migrations(version TEXT PRIMARY KEY);
        INSERT INTO schema_migrations VALUES ('001_initial.sql');
        INSERT INTO usuarios VALUES (1,'Admin','admin','hash','Administrador',1);
        INSERT INTO clientes(id,nome,cpf) VALUES (1,'Cliente','52998224725');
        INSERT INTO veiculos(id,cliente_id,placa,marca,modelo,ano) VALUES (1,1,'ABC1234','Marca','Modelo',2020);
        INSERT INTO pecas VALUES (1,'Filtro',100,5,1);
        INSERT INTO movimentacoes_estoque(id,peca_id,usuario_id,tipo,quantidade) VALUES (1,1,1,'Entrada',5);
        INSERT INTO ordens_servico(id,cliente_id,veiculo_id,problema,status) VALUES (1,1,1,'Revisão','Aberta');
        INSERT INTO historico_status_os(os_id,usuario_id,novo) VALUES (1,1,'Aberta');
    """)
    before = dict(c.execute("SELECT * FROM movimentacoes_estoque").fetchone())
    c.close()
    db.migrate()
    db.migrate()
    with db.transaction() as c:
        assert dict(c.execute("SELECT * FROM movimentacoes_estoque").fetchone()) == before
        assert c.execute("SELECT estoque FROM pecas").fetchone()[0] == 5
        assert c.execute("SELECT status FROM ordens_servico").fetchone()[0] == "Em orçamento"
        assert [r[0] for r in c.execute("SELECT novo FROM historico_status_os ORDER BY id")] == [
            "Aberta",
            "Em orçamento",
        ]
        assert not c.execute("PRAGMA foreign_key_check").fetchall()
