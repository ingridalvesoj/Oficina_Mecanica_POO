import pytest

from oficina.domain import validators as v
from oficina.domain.entities import Administrador, Mecanico
from oficina.domain.exceptions import CampoObrigatorioError, ValidacaoError


@pytest.mark.parametrize("value", ["", "   ", None])
def test_required(value):
    with pytest.raises(CampoObrigatorioError):
        v.required(value, "o nome")


@pytest.mark.parametrize("value", ["11111111111", "52998224724", "123", "abc52998224725"])
def test_invalid_cpf(value):
    with pytest.raises(ValidacaoError):
        v.cpf(value)


def test_normalization():
    assert v.cpf("529.982.247-25") == "52998224725"
    assert v.plate("abc-1234") == "ABC1234"
    assert v.plate("abc1d23") == "ABC1D23"
    assert v.cents("1234,56") == 123456
    assert v.cents("0.10") == 10


@pytest.mark.parametrize("value", ["-1", "1.001", "NaN", "Infinity", "1.234,56", "abc"])
def test_invalid_money(value):
    with pytest.raises(ValidacaoError):
        v.cents(value)


def test_polymorphism():
    admin = Administrador(1, "Admin", "admin")
    mechanic = Mecanico(2, "Mecânico", "mec")
    assert admin.permite("administrar", 2)
    assert mechanic.permite("executar", 2)
    assert not mechanic.permite("administrar", 2)
    assert not mechanic.permite("executar", 3)
