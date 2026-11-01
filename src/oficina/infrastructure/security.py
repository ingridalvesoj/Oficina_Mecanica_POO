import hashlib
import hmac
import secrets

from oficina.domain.exceptions import ValidacaoError

ITERATIONS = 600_000


def hash_password(password: str) -> str:
    if len(password) < 10 or len(password) > 128:
        raise ValidacaoError("A senha deve ter entre 10 e 128 caracteres.")
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
