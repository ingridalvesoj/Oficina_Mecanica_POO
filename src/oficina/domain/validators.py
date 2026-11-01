import re
from datetime import date
from decimal import Decimal, InvalidOperation

from .exceptions import CampoObrigatorioError, ValidacaoError


def required(value: str, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CampoObrigatorioError(f"Informe {field}.")
    if len(text) > 2000:
        raise ValidacaoError(f"O campo {field} excede 2.000 caracteres.")
    return text


def cpf(value: str) -> str:
    value = required(value, "o CPF")
    if not re.fullmatch(r"[\d.\-\s]+", value):
        raise ValidacaoError("Informe um CPF válido.")
    digits = re.sub(r"\D", "", value)
    if len(digits) != 11 or len(set(digits)) == 1:
        raise ValidacaoError("Informe um CPF válido.")
    for length in (9, 10):
        total = sum(int(digits[i]) * (length + 1 - i) for i in range(length))
        expected = (total * 10 % 11) % 10
        if expected != int(digits[length]):
            raise ValidacaoError("Informe um CPF válido.")
    return digits


def plate(value: str) -> str:
    normalized = required(value, "a placa").upper().replace("-", "").replace(" ", "")
    if not re.fullmatch(r"[A-Z]{3}(?:[0-9]{4}|[0-9][A-Z][0-9]{2})", normalized):
        raise ValidacaoError("Informe uma placa válida (ABC1234 ou ABC1D23).")
    return normalized


def email(value: str) -> str:
    value = str(value or "").strip()
    if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value):
        raise ValidacaoError("Informe um e-mail válido.")
    return value


def integer(value: int, field: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValidacaoError(f"{field} deve ser um inteiro maior ou igual a {minimum}.")
    if value > 1_000_000_000:
        raise ValidacaoError(f"{field} excede o limite permitido.")
    return value


def year(value: int) -> int:
    integer(value, "Ano", 1886)
    if value > date.today().year + 1:
        raise ValidacaoError("Ano do veículo inválido.")
    return value


def cents(value: str) -> int:
    """Converte entrada decimal sem usar float; aceita 1234,56 ou 1234.56."""
    raw = required(value, "o valor").replace(",", ".")
    try:
        number = Decimal(raw)
        if not number.is_finite() or number < 0 or number * 100 != (number * 100).to_integral():
            raise ValueError
        return integer(int(number * 100), "Valor em centavos")
    except (InvalidOperation, ValueError, OverflowError):
        raise ValidacaoError("Informe um valor não negativo com até duas casas decimais.") from None
