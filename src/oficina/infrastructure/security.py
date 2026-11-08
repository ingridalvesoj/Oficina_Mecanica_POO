import hashlib
import hmac
import secrets

from oficina.domain.exceptions import ValidacaoError

ITERATIONS = 600_000


def hash_password(password: str) -> str:
    if (
        len(password) < 8
        or not any(char.isupper() for char in password)
        or not any(char.islower() for char in password)
        or not any(not char.isalnum() and not char.isspace() for char in password)
    ):
        raise ValidacaoError(
            "A senha deve ter no mínimo 8 caracteres, uma letra maiúscula, uma minúscula e um caractere especial."
        )
    if len(password) > 128:
        raise ValidacaoError("A senha informada é muito longa. Escolha uma senha mais curta.")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), ITERATIONS).hex()
    return f"pbkdf2_sha256${ITERATIONS}${salt}${digest}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256" or len(password) > 128:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(iterations)
        ).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False
