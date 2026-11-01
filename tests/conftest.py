import pytest

from oficina.application.auth_service import AuthService
from oficina.application.cadastro_service import CadastroService
from oficina.application.estoque_service import EstoqueService
from oficina.application.ordem_service import OrdemService
from oficina.domain.enums import Perfil
from oficina.infrastructure.database import Database


@pytest.fixture
def system(tmp_path):
    db = Database(tmp_path / "test.sqlite3")
    db.migrate()
    auth = AuthService(db)
    admin = auth.bootstrap("Administrador de teste", "admin", "senha-teste-segura")
    catalog, stock, orders = CadastroService(db), EstoqueService(db), OrdemService(db)
    mechanic = catalog.save(
        admin,
        "usuarios",
        {
            "nome": "Mecânico teste",
            "login": "mecanico",
            "senha": "senha-teste-segura",
            "perfil": Perfil.MECANICO,
        },
    )
    client = catalog.save(admin, "clientes", {"nome": "Cliente teste", "cpf": "52998224725"})
    vehicle = catalog.save(
        admin,
        "veiculos",
        {
            "cliente_id": client,
            "placa": "ABC1D23",
            "marca": "Marca",
            "modelo": "Modelo",
            "ano": 2020,
        },
    )
    part = catalog.save(admin, "pecas", {"descricao": "Filtro", "valor_centavos": 2590})
    service = catalog.save(
        admin, "servicos", {"descricao": "Troca de filtro", "valor_centavos": 10000}
    )
    stock.enter(admin, part, 10, "Estoque inicial de teste")
    return dict(
        db=db,
        auth=auth,
        catalog=catalog,
        stock=stock,
        orders=orders,
        admin=admin,
        mechanic=mechanic,
        client=client,
        vehicle=vehicle,
        part=part,
        service=service,
    )


def create_order(s, mechanic=True):
    return s["orders"].create(
        s["admin"],
        s["client"],
        s["vehicle"],
        "Revisão do motor",
        s["mechanic"] if mechanic else None,
    )


def execute_order(s, order_id):
    for status in ("Em orçamento", "Aguardando aprovação", "Aprovada", "Em execução"):
        s["orders"].transition(s["admin"], order_id, status)


def complete_order(s, order_id):
    execute_order(s, order_id)
    for item in s["orders"].detail(s["admin"], order_id)["order"].servicos:
        s["orders"].update_service(s["mechanic"], order_id, item.id, "Em execução")
        s["orders"].update_service(s["mechanic"], order_id, item.id, "Finalizado")
    s["orders"].transition(s["mechanic"], order_id, "Concluída")
