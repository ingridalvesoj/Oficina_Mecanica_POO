import sqlite3

import pytest
from conftest import create_order

from oficina.domain.exceptions import CarregamentoError, PersistenciaError, ValidacaoError
from oficina.infrastructure.database import Database


def test_migration_idempotence_and_constraints(system):
    s = system
    s["db"].migrate()
    s["db"].migrate()
    with s["db"].transaction() as c:
        assert c.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert c.execute("SELECT COUNT(*) FROM schema_migrations").fetchone()[0] == 3
        assert c.execute("SELECT COUNT(*) FROM clientes").fetchone()[0] == 1
    with pytest.raises(ValidacaoError):
        with s["db"].transaction(write=True) as c:
            c.execute("UPDATE pecas SET estoque=-1")


def test_read_and_write_failures(tmp_path):
    db = Database(tmp_path / "missing" / "db.sqlite3")
    with pytest.raises(CarregamentoError):
        with db.transaction():
            pass
    with pytest.raises(PersistenciaError):
        with db.transaction(write=True):
            pass


def test_sql_failure_rolls_back_items_stock_and_audit(system):
    s = system
    oid = create_order(s)
    with s["db"].transaction(write=True) as c:
        c.execute("""CREATE TRIGGER simulate_failure BEFORE INSERT ON auditoria_os
            BEGIN SELECT RAISE(ABORT, 'simulated storage failure'); END""")
    with pytest.raises(ValidacaoError):
        s["orders"].add_part(s["admin"], oid, s["part"], 4)
    assert not s["orders"].detail(s["admin"], oid)["order"].pecas
    assert s["stock"].balances(s["admin"])[0]["disponivel"] == 10
    assert len(s["stock"].history(s["admin"])) == 1


def test_operational_error_maps_to_safe_message(system, monkeypatch):
    def fail():
        raise sqlite3.OperationalError("private/path/database failure")

    monkeypatch.setattr(system["db"], "connect", fail)
    with pytest.raises(CarregamentoError, match="Não foi possível carregar"):
        system["orders"].list(system["admin"])
    with pytest.raises(PersistenciaError, match="Não foi possível salvar"):
        system["stock"].enter(system["admin"], system["part"], 1, "Teste")
