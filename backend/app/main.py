import uvicorn
import logging
import re
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.config import settings
from app.database.session import engine, Base
from app.database import models
from app.database.migrations import run_migrations
from app.api.endpoints import router as api_router
from app.api.zoho_api import router as zoho_router
from app.api.auth import router as auth_router, get_or_sync_admin
from fastapi.responses import JSONResponse
from fastapi import Request


class SensitiveDataFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # Sanitize record.msg if it is a string
        if isinstance(record.msg, str):
            record.msg = self.sanitize_string(record.msg)
            
        # Sanitize record.args if they exist
        if record.args:
            new_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    new_args.append(self.sanitize_string(arg))
                else:
                    new_args.append(arg)
            record.args = tuple(new_args)
            
        return True

    def sanitize_string(self, text: str) -> str:
        # 1. Sanitize OAuth authorization code in query parameters (e.g. code=...)
        text = re.sub(r'code=[a-zA-Z0-9_\-\.]+', 'code=[REDACTED]', text)
        
        # 2. Sanitize client_secret
        text = re.sub(r'client_secret=[a-zA-Z0-9_\-\.]+', 'client_secret=[REDACTED]', text)
        
        # 3. Sanitize access_token or refresh_token
        text = re.sub(r'access_token=[a-zA-Z0-9_\-\.]+', 'access_token=[REDACTED]', text)
        text = re.sub(r'refresh_token=[a-zA-Z0-9_\-\.]+', 'refresh_token=[REDACTED]', text)
        
        # 4. Sanitize Authorization header (e.g. Authorization: Bearer ... or Authorization: token)
        text = re.sub(r'(?i)Authorization:\s*(?:Bearer\s+)?[^\s]+', 'Authorization: [REDACTED]', text)
        
        return text

def setup_logging():
    sensitive_filter = SensitiveDataFilter()
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.addFilter(sensitive_filter)
    for handler in root_logger.handlers:
        handler.addFilter(sensitive_filter)
        
    # Configure uvicorn loggers
    for name in ["uvicorn", "uvicorn.access", "uvicorn.error"]:
        logger = logging.getLogger(name)
        logger.addFilter(sensitive_filter)
        for handler in logger.handlers:
            handler.addFilter(sensitive_filter)

# Initial setup at import time
setup_logging()

# Initialize database schema
# For this phase, tables are automatically initialized on launch.
Base.metadata.create_all(bind=engine)
run_migrations(engine)


app = FastAPI(
    title="AUTO-ZOHO API",
    description="Automated system for parsing, validating, and uploading expenses from spreadsheets.",
    version="1.0.0"
)

# Apply CORS middleware settings to authorize the React client requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def csrf_middleware(request: Request, call_next):
    # Only enforce on state-changing requests and when not testing
    import sys
    csrf_enforced = getattr(settings, "CSRF_ENFORCED", False) or ("pytest" not in sys.modules and settings.ENV != "test")
    if request.method in ["POST", "PUT", "PATCH", "DELETE"] and csrf_enforced:
        path = request.url.path
        public_paths = [
            "/api/auth/login",
            "/api/auth/initialize",
            "/api/auth/forgot-password",
            "/api/auth/verify-otp",
            "/api/auth/reset-password",
            "/api/auth/status"
        ]
        if not any(path.startswith(p) for p in public_paths):
            csrf_cookie = request.cookies.get("csrf_token")
            csrf_header = request.headers.get("x-csrf-token")
            
            if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "CSRF validation failed. Missing or mismatched CSRF token."}
                )
                
    response = await call_next(request)
    return response

# Register endpoints router
app.include_router(auth_router, prefix="/api")
app.include_router(api_router, prefix="/api")
app.include_router(zoho_router, prefix="/api/zoho", tags=["zoho"])

@app.on_event("startup")
def on_startup():
    setup_logging()
    # Sync or precreate single admin identity
    from app.database.session import SessionLocal
    db = SessionLocal()
    try:
        get_or_sync_admin(db)
    finally:
        db.close()


if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=True)
