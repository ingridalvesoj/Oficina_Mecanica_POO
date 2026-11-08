from io import BytesIO

import pytest
from conftest import complete_order, create_order
from pypdf import PdfReader

from oficina.config import ROOT
from oficina.domain.exceptions import PermissaoNegadaError, ValidacaoError
from oficina.infrastructure.database import Database
from oficina.infrastructure.security import hash_password, verify_password


@pytest.mark.parametrize("password", ["Senha12!", "Abc1234@", "Abcdefgh#"])
def test_new_password_policy(password):
    assert verify_password(password, hash_password(password))


@pytest.mark.parametrize("password", ["abc123!", "abcdefgh", "abcdefgh "])
def test_reject_password_without_minimum_or_symbol(password):
    with pytest.raises(ValidacaoError, match="mínimo 8 caracteres"):
        hash_password(password)


def test_optional_stock_reason_and_id_order(system):
    s = system
    second = s["catalog"].save(
        s["admin"], "pecas", {"descricao": "Antes alfabeticamente", "valor_centavos": 500}
    )
    s["stock"].enter(s["admin"], second, 2)
    balances = s["stock"].balances(s["admin"])
    assert [p["id"] for p in balances] == [s["part"], second]
    assert s["stock"].history(s["admin"])[0]["justificativa"] == ""


def test_debit_payment_and_pdf_permissions(system):
    s = system
    oid = create_order(s)
    s["orders"].add_service(s["admin"], oid, s["service"])
    complete_order(s, oid)
    s["orders"].invoice(s["admin"], oid)
    s["orders"].pay(s["admin"], oid, 10000, "Débito")
    admin_pdf = s["orders"].export_pdf(s["admin"], oid)
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(admin_pdf)).pages)
    assert "Débito" in text and "Cliente teste" in text and "100,00" in text
    mechanic_pdf = s["orders"].export_pdf(s["mechanic"], oid)
    text = "\n".join(p.extract_text() for p in PdfReader(BytesIO(mechanic_pdf)).pages)
    assert "Faturamento:" not in text and "Pagamento:" not in text
    other = create_order(s, mechanic=False)
    with pytest.raises(PermissaoNegadaError):
        s["orders"].export_pdf(s["mechanic"], other)


def test_pdf_long_order_and_markup(system):
    s = system
    oid = create_order(s)
    service = s["catalog"].save(
        s["admin"],
        "servicos",
        {"descricao": "Inspeção <motor> & revisão " * 8, "valor_centavos": 100},
    )
    for _ in range(30):
        s["orders"].add_service(s["admin"], oid, service)
    reader = PdfReader(BytesIO(s["orders"].export_pdf(s["admin"], oid)))
    assert len(reader.pages) > 1
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert "<motor>" in text and "Total da OS: R$ 30,00" in text
    assert all("Página" in page.extract_text() for page in reader.pages)


def test_upgrade_preserves_existing_transfer_payment(tmp_path):
    db = Database(tmp_path / "legacy.sqlite3")
    connection = db.connect()
    connection.executescript((ROOT / "migrations/001_initial.sql").read_text(encoding="utf-8"))
    connection.executescript("""
        CREATE TABLE schema_migrations(version TEXT PRIMARY KEY);
        INSERT INTO schema_migrations VALUES ('001_initial.sql');
        INSERT INTO usuarios(id,nome,login,senha_hash,perfil) VALUES (1,'Admin','admin','hash','Administrador');
        INSERT INTO clientes(id,nome,cpf) VALUES (1,'Cliente','52998224725');
        INSERT INTO veiculos(id,cliente_id,placa,marca,modelo,ano) VALUES (1,1,'ABC1234','Marca','Modelo',2020);
        INSERT INTO ordens_servico(id,cliente_id,veiculo_id,problema,status) VALUES (1,1,1,'Revisão','Concluída');
        INSERT INTO faturamentos(id,os_id,valor_centavos,usuario_id) VALUES (1,1,10000,1);
        INSERT INTO pagamentos(id,faturamento_id,valor_centavos,forma,usuario_id) VALUES (1,1,10000,'Transferência',1);
    """)
    connection.close()
    db.migrate()
    db.migrate()
    with db.transaction() as c:
        assert c.execute("SELECT forma,valor_centavos FROM pagamentos").fetchone()[:] == (
            "Transferência",
            10000,
        )
        assert not c.execute("PRAGMA foreign_key_check").fetchall()
