import datetime
from fastapi import Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database import models
from app.security.auth_utils import hash_token
from app.config.config import settings

def get_current_admin(
    request: Request,
    db: Session = Depends(get_db)
) -> models.AdminAuth:
    # 1. Get session token from cookie
    session_token = request.cookies.get("session_token")
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication session token is missing."
        )
        
    # 2. Hash token and query database
    token_hash = hash_token(session_token)
    session_record = db.query(models.AuthSession).filter(
        models.AuthSession.id == session_token,
        models.AuthSession.session_token_hash == token_hash
    ).first()
    
    if not session_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or active session not found."
        )
        
    if session_record.revoked_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has been logged out/revoked."
        )
        
    # 3. Check absolute session expiration
    now = datetime.datetime.utcnow()
    if session_record.expires_at < now:
        # Session expired
        db.delete(session_record)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired."
        )
        
    # 4. Check inactivity timeout (30 minutes)
    inactivity_limit = session_record.last_activity_at + datetime.timedelta(minutes=30)
    if inactivity_limit < now:
        # Revoke session due to inactivity
        db.delete(session_record)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired due to inactivity."
        )
        
    # 5. Update last activity (sliding window)
    session_record.last_activity_at = now
    session_record.expires_at = now + datetime.timedelta(minutes=30)
    db.commit()
    
    # 6. Return the admin
    admin = db.query(models.AdminAuth).filter(models.AdminAuth.id == session_record.admin_id).first()
    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Associated administrator account not found."
        )
        
    return admin
