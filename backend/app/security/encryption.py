import base64
from cryptography.fernet import Fernet
from app.config.config import settings

def _get_fernet() -> Fernet:
    """Helper to instantiate Fernet cipher using the settings key."""
    # Ensure key is correctly padded/encoded as bytes
    key = settings.ZOHO_TOKEN_ENCRYPTION_KEY.encode()
    return Fernet(key)

def encrypt_token(raw_token: str) -> str:
    """
    Encrypts a raw string token into ciphertext.
    Returns:
        A base64 encoded encrypted string.
    """
    if not raw_token:
        return ""
    cipher = _get_fernet()
    encrypted_bytes = cipher.encrypt(raw_token.encode())
    return encrypted_bytes.decode()

def decrypt_token(encrypted_token: str) -> str:
    """
    Decrypts base64 encoded ciphertext back to a raw string.
    Returns:
        The decrypted string value.
    """
    if not encrypted_token:
        return ""
    cipher = _get_fernet()
    decrypted_bytes = cipher.decrypt(encrypted_token.encode())
    return decrypted_bytes.decode()

def hash_pin(pin: str) -> str:
    """Hashes a local application PIN passcode using PBKDF2-HMAC-SHA256."""
    import hashlib
    import os
    if not pin:
        return ""
    salt = os.urandom(16)
    pwdhash = hashlib.pbkdf2_hmac('sha256', pin.encode('utf-8'), salt, 100000)
    return salt.hex() + ":" + pwdhash.hex()

def verify_pin(pin: str, hashed_pin: str) -> bool:
    """Verifies a plaintext passcode against the hex-encoded salted hash."""
    import hashlib
    if not pin or not hashed_pin or ":" not in hashed_pin:
        return False
    try:
        salt_hex, hash_hex = hashed_pin.split(":")
        salt = bytes.fromhex(salt_hex)
        pwdhash = hashlib.pbkdf2_hmac('sha256', pin.encode('utf-8'), salt, 100000)
        return pwdhash.hex() == hash_hex
    except Exception:
        return False
