import datetime
import random
import secrets
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status, BackgroundTasks
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.database import models
from app.api.deps import get_current_admin
from app.security.auth_utils import hash_password, verify_password, generate_random_token, hash_token
from app.config.config import settings
from app.services.email import send_reset_code_email

router = APIRouter(prefix="/auth", tags=["auth"])

# Pydantic Schemas for Requests
class InitializePayload(BaseModel):
    new_password: str
    confirm_password: str
    initialization_secret: str

class LoginPayload(BaseModel):
    username: str
    password: str

class VerifyOtpPayload(BaseModel):
    otp: str

class ResetPasswordPayload(BaseModel):
    reset_token: str
    new_password: str
    confirm_password: str

class ChangePasswordPayload(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str

# Helper to sync admin from environment variables
def get_or_sync_admin(db: Session) -> models.AdminAuth:
    username = settings.AUTO_ZOHO_ADMIN_USERNAME or "admin"
    email = settings.AUTO_ZOHO_ADMIN_EMAIL or "admin@example.com"
    
    admin = db.query(models.AdminAuth).first()
    if not admin:
        admin = models.AdminAuth(
            username=username,
            email=email,
            password_initialized=False
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
    else:
        # Sync env settings if changed
        if admin.username != username or admin.email != email:
            admin.username = username
            admin.email = email
            db.commit()
            db.refresh(admin)
            
    # Enforce exactly one row
    extra_admins = db.query(models.AdminAuth).filter(models.AdminAuth.id != admin.id).all()
    if extra_admins:
        for extra in extra_admins:
            db.delete(extra)
        db.commit()
        
    return admin

@router.get("/status")
def get_auth_status(request: Request, response: Response, db: Session = Depends(get_db)):
    """Checks the initialization status of the admin and whether currently authenticated."""
    admin = get_or_sync_admin(db)
    
    # Check if a valid session exists
    authenticated = False
    session_token = request.cookies.get("session_token")
    if session_token:
        token_hash = hash_token(session_token)
        session_record = db.query(models.AuthSession).filter(
            models.AuthSession.id == session_token,
            models.AuthSession.session_token_hash == token_hash,
            models.AuthSession.revoked_at.is_(None)
        ).first()
        
        if session_record:
            now = datetime.datetime.utcnow()
            # Verify absolute expiration and sliding inactivity
            if session_record.expires_at > now and (session_record.last_activity_at + datetime.timedelta(minutes=30)) > now:
                authenticated = True
                
    # Always set/refresh CSRF cookie on status check if not present
    csrf_token = request.cookies.get("csrf_token")
    if not csrf_token:
        csrf_token = secrets.token_urlsafe(32)
        # Non-HttpOnly cookie so React frontend can read it to send in headers
        response.set_cookie(
            "csrf_token",
            csrf_token,
            secure=settings.ENV not in ["development", "test"],
            samesite="lax",
            path="/"
        )
        
    return {
        "initialized": admin.password_initialized,
        "authenticated": authenticated,
        "username": admin.username if authenticated else None,
        "email": admin.email if authenticated else None
    }

@router.post("/initialize")
def initialize_admin_password(payload: InitializePayload, db: Session = Depends(get_db)):
    """One-time setup for the administrator's password, requiring the initialization secret."""
    admin = get_or_sync_admin(db)
    if admin.password_initialized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Administrator password has already been initialized."
        )
        
    # Verify initialization secret
    if not settings.ADMIN_INITIALIZATION_SECRET or payload.initialization_secret != settings.ADMIN_INITIALIZATION_SECRET:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid initialization secret."
        )
        
    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long."
        )
        
    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match."
        )
        
    admin.password_hash = hash_password(payload.new_password)
    admin.password_initialized = True
    db.commit()
    
    return {"status": "success", "message": "Admin password initialized successfully."}

@router.post("/login")
def login(payload: LoginPayload, request: Request, response: Response, db: Session = Depends(get_db)):
    """Authenticates the administrator, sets session cookies, and registers session details."""
    admin = get_or_sync_admin(db)
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    
    # 1. Rate Limiting: Check failed attempts for IP in the last 15 minutes
    fifteen_mins_ago = datetime.datetime.utcnow() - datetime.timedelta(minutes=15)
    failed_attempts = db.query(models.LoginAttempt).filter(
        models.LoginAttempt.ip_address == client_ip,
        models.LoginAttempt.successful.is_(False),
        models.LoginAttempt.timestamp >= fifteen_mins_ago
    ).count()
    
    if failed_attempts >= 5:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed login attempts. Please wait 15 minutes."
        )
        
    # 2. Verify Credentials
    success = False
    if admin.password_initialized and payload.username == admin.username:
        success = verify_password(payload.password, admin.password_hash or "")
        
    # 3. Log Login Attempt
    attempt = models.LoginAttempt(
        ip_address=client_ip,
        successful=success
    )
    db.add(attempt)
    db.commit()
    
    if not success:
        # Generic error message to prevent account enumeration/discovery
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid username or password."
        )
        
    # Clear failed attempts on successful login
    db.query(models.LoginAttempt).filter(
        models.LoginAttempt.ip_address == client_ip
    ).delete()
    
    # 4. Generate Session
    raw_token = generate_random_token()
    token_hash = hash_token(raw_token)
    
    now = datetime.datetime.utcnow()
    session = models.AuthSession(
        id=raw_token,
        admin_id=admin.id,
        session_token_hash=token_hash,
        created_at=now,
        expires_at=now + datetime.timedelta(minutes=30),
        last_activity_at=now,
        ip_address=client_ip,
        user_agent=user_agent
    )
    db.add(session)
    
    # Update last login time
    admin.last_login_at = now
    db.commit()
    
    response.set_cookie(
        "session_token",
        raw_token,
        httponly=True,
        secure=settings.ENV not in ["development", "test"],
        samesite="lax",
        path="/"
    )
    
    csrf_token = secrets.token_urlsafe(32)
    response.set_cookie(
        "csrf_token",
        csrf_token,
        secure=settings.ENV not in ["development", "test"],
        samesite="lax",
        path="/"
    )
    
    return {"status": "success", "message": "Logged in successfully."}

@router.post("/logout")
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """Revokes the current session and clears cookies."""
    session_token = request.cookies.get("session_token")
    if session_token:
        token_hash = hash_token(session_token)
        session_record = db.query(models.AuthSession).filter(
            models.AuthSession.id == session_token,
            models.AuthSession.session_token_hash == token_hash
        ).first()
        
        if session_record:
            db.delete(session_record)
            db.commit()
            
    response.delete_cookie("session_token", path="/")
    response.delete_cookie("csrf_token", path="/")
    
    return {"status": "success", "message": "Logged out successfully."}

@router.post("/forgot-password")
def request_password_reset(background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """Requests a password reset code. Sends a 6-digit verification code to the admin email."""
    admin = get_or_sync_admin(db)
    
    # Rate Limiting: 60 seconds cooldown between reset requests
    one_min_ago = datetime.datetime.utcnow() - datetime.timedelta(seconds=60)
    recent_token = db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.admin_id == admin.id,
        models.PasswordResetToken.created_at >= one_min_ago
    ).first()
    
    if recent_token:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Please wait 60 seconds before requesting another reset code."
        )
        
    # Generate 6-digit OTP
    otp = f"{random.randint(100000, 999999)}"
    otp_hash = hash_token(otp)
    
    # Invalidate existing active reset tokens
    db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.admin_id == admin.id,
        models.PasswordResetToken.used_at.is_(None)
    ).update({"used_at": datetime.datetime.utcnow()}, synchronize_session=False)
    
    now = datetime.datetime.utcnow()
    token_record = models.PasswordResetToken(
        admin_id=admin.id,
        token_hash=otp_hash,
        created_at=now,
        expires_at=now + datetime.timedelta(minutes=10),
        attempt_count=0
    )
    db.add(token_record)
    db.commit()
    
    # Send email in a background task
    background_tasks.add_task(send_reset_code_email, admin.email, otp)
    
    # Standard security feedback
    return {
        "status": "success", 
        "message": "If a password reset is available, a verification code will be sent to the registered recovery email."
    }

@router.post("/verify-otp")
def verify_reset_otp(payload: VerifyOtpPayload, db: Session = Depends(get_db)):
    """Verifies the 6-digit OTP and returns a short-lived reset token on success."""
    admin = get_or_sync_admin(db)
    
    # Find latest active reset token
    token_record = db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.admin_id == admin.id,
        models.PasswordResetToken.used_at.is_(None)
    ).order_by(models.PasswordResetToken.created_at.desc()).first()
    
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active password reset request found."
        )
        
    # Check expiration
    if token_record.expires_at < datetime.datetime.utcnow():
        token_record.used_at = datetime.datetime.utcnow()
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code has expired."
        )
        
    # Check rate limiting: max 5 attempts per reset token
    if token_record.attempt_count >= 5:
        token_record.used_at = datetime.datetime.utcnow()
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum attempts exceeded. Please request a new code."
        )
        
    # Increment attempts
    token_record.attempt_count += 1
    db.commit()
    
    # Verify OTP
    input_hash = hash_token(payload.otp)
    if token_record.token_hash != input_hash:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code."
        )
        
    # OTP is verified! Generate a short-lived password reset token
    raw_reset_token = generate_random_token()
    reset_token_hash = hash_token(raw_reset_token)
    
    token_record.token_hash = reset_token_hash
    token_record.expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=5)
    token_record.attempt_count = 0
    db.commit()
    
    return {"status": "success", "reset_token": raw_reset_token}

@router.post("/reset-password")
def reset_password(payload: ResetPasswordPayload, db: Session = Depends(get_db)):
    """Resets the administrator's password using a valid reset token."""
    admin = get_or_sync_admin(db)
    
    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long."
        )
        
    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match."
        )
        
    # Find matching reset token
    token_hash = hash_token(payload.reset_token)
    token_record = db.query(models.PasswordResetToken).filter(
        models.PasswordResetToken.token_hash == token_hash,
        models.PasswordResetToken.used_at.is_(None)
    ).first()
    
    if not token_record:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token."
        )
        
    if token_record.expires_at < datetime.datetime.utcnow():
        token_record.used_at = datetime.datetime.utcnow()
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset token has expired."
        )
        
    # Apply new password
    admin.password_hash = hash_password(payload.new_password)
    
    # Mark token used
    token_record.used_at = datetime.datetime.utcnow()
    
    # Invalidate all active sessions for this administrator
    db.query(models.AuthSession).filter(
        models.AuthSession.admin_id == admin.id
    ).delete()
    
    db.commit()
    
    return {"status": "success", "message": "Password reset successfully."}

@router.post("/change-password")
def change_password(
    payload: ChangePasswordPayload,
    request: Request,
    admin: models.AdminAuth = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Changes the logged-in administrator's password and revokes all other active sessions."""
    if not verify_password(payload.current_password, admin.password_hash or ""):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect current password."
        )
        
    if len(payload.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be at least 8 characters long."
        )
        
    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match."
        )
        
    admin.password_hash = hash_password(payload.new_password)
    
    # Invalidate all other active sessions
    current_session = request.cookies.get("session_token")
    if current_session:
        db.query(models.AuthSession).filter(
            models.AuthSession.admin_id == admin.id,
            models.AuthSession.id != current_session
        ).delete()
        
    db.commit()
    
    return {"status": "success", "message": "Password updated successfully."}
