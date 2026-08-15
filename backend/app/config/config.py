import os
from typing import List
from pydantic_settings import BaseSettings

# Base directory of the project
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

class Settings(BaseSettings):
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    ENV: str = "development"
    
    # Database
    DATABASE_URL: str = f"sqlite:///{os.path.join(BASE_DIR, 'data', 'zoho_uploader.db')}"
    
    # Local Storage directories
    UPLOAD_DIR: str = os.path.join(BASE_DIR, "data", "uploads")
    LOGS_DIR: str = os.path.join(BASE_DIR, "logs")
    
    # CORS Origins
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173"
    
    # Zoho Expense API Configuration
    ZOHO_CLIENT_ID: str = ""
    ZOHO_CLIENT_SECRET: str = ""
    ZOHO_REDIRECT_URI: str = "http://localhost:8000/api/zoho/callback"
    ZOHO_ACCOUNTS_URL: str = "https://accounts.zoho.com"
    ZOHO_API_URL: str = "https://www.zohoapis.com/expense/v1"
    ZOHO_TOKEN_ENCRYPTION_KEY: str = ""

    class Config:
        env_file = os.path.join(BASE_DIR, ".env")
        extra = "ignore"

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

settings = Settings()

# Ensure we have a valid Token Encryption Key
if not settings.ZOHO_TOKEN_ENCRYPTION_KEY:
    try:
        from cryptography.fernet import Fernet
        generated_key = Fernet.generate_key().decode()
    except Exception:
        # Temporary fallback during setup if package not loaded yet
        generated_key = "aG9tZV9kZXZlbG9wZW1lbnRfcm9idXN0X2tleV8xMjM0NTY3OA=="
        
    settings.ZOHO_TOKEN_ENCRYPTION_KEY = generated_key
    env_file_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_file_path):
        try:
            with open(env_file_path, "a") as f:
                f.write(f"\nZOHO_TOKEN_ENCRYPTION_KEY={generated_key}\n")
        except Exception:
            pass


# Ensure directories exist
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.LOGS_DIR, exist_ok=True)
