from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
import secrets
import hashlib

ph = PasswordHasher()

def hash_password(password: str) -> str:
    """Hashes a password using Argon2id."""
    return ph.hash(password)

def verify_password(password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against the Argon2id hash."""
    if not password or not hashed_password:
        return False
    try:
        return ph.verify(hashed_password, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False

def generate_random_token() -> str:
    """Generates a cryptographically secure random token."""
    return secrets.token_urlsafe(32)

def hash_token(token: str) -> str:
    """Generates a SHA-256 hash of the token."""
    return hashlib.sha256(token.encode()).hexdigest()
