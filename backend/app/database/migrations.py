from sqlalchemy import inspect, text
import logging

logger = logging.getLogger("app.database.migrations")

def run_migrations(engine):
    """
    Checks the schema of existing tables and safely applies migrations
    for columns introduced in subsequent phases (specifically 'scopes' in 'zoho_credentials').
    Does not delete or modify existing tables or data.
    """
    inspector = inspect(engine)
    
    # 1. Check zoho_credentials table
    if "zoho_credentials" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("zoho_credentials")]
        
        # Check for missing 'scopes' column
        if "scopes" not in columns:
            logger.info("Database migration: 'scopes' column missing in 'zoho_credentials'. Running migration...")
            try:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE zoho_credentials ADD COLUMN scopes VARCHAR(500) DEFAULT ''"))
                logger.info("Database migration: Successfully added 'scopes' column to 'zoho_credentials'.")
            except Exception as e:
                logger.error(f"Database migration failed for 'scopes' column: {e}")
                raise e
        else:
            logger.debug("Database migration: 'scopes' column already exists in 'zoho_credentials'.")
    else:
        logger.debug("Database migration: 'zoho_credentials' table does not exist yet. It will be created by SQLAlchemy metadata.")

    # 2. Check expense_records table
    if "expense_records" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("expense_records")]
        
        # Check for missing columns
        if "zoho_status" not in columns:
            logger.info("Database migration: tracking columns missing in 'expense_records'. Running migration...")
            try:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE expense_records ADD COLUMN zoho_status VARCHAR(50) DEFAULT 'PENDING'"))
                    conn.execute(text("ALTER TABLE expense_records ADD COLUMN zoho_expense_id VARCHAR(100) NULL"))
                    conn.execute(text("ALTER TABLE expense_records ADD COLUMN zoho_error TEXT NULL"))
                    conn.execute(text("ALTER TABLE expense_records ADD COLUMN destination_report_id VARCHAR(100) NULL"))
                logger.info("Database migration: Successfully added tracking columns to 'expense_records'.")
            except Exception as e:
                logger.error(f"Database migration failed for 'expense_records' tracking columns: {e}")
                raise e
        else:
            logger.debug("Database migration: tracking columns already exist in 'expense_records'.")
            
    # 3. Check zoho_audit_logs table
    if "zoho_audit_logs" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("zoho_audit_logs")]
        
        # Check for missing column
        if "session_id" not in columns:
            logger.info("Database migration: 'session_id' column missing in 'zoho_audit_logs'. Running migration...")
            try:
                with engine.begin() as conn:
                    conn.execute(text("ALTER TABLE zoho_audit_logs ADD COLUMN session_id INTEGER NULL"))
                logger.info("Database migration: Successfully added 'session_id' column to 'zoho_audit_logs'.")
            except Exception as e:
                logger.error(f"Database migration failed for 'session_id' column: {e}")
                raise e
        else:
            logger.debug("Database migration: 'session_id' column already exists in 'zoho_audit_logs'.")

    # 4. Check upload_sessions table additional columns
    if "upload_sessions" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("upload_sessions")]
        with engine.begin() as conn:
            if "upload_session_id" not in columns:
                try:
                    conn.execute(text("ALTER TABLE upload_sessions ADD COLUMN upload_session_id VARCHAR(50) NULL"))
                    logger.info("Database migration: Added 'upload_session_id' to 'upload_sessions'.")
                except Exception as e:
                    logger.error(f"Migration failed for 'upload_session_id': {e}")
            if "selected_gst_report_id" not in columns:
                try:
                    conn.execute(text("ALTER TABLE upload_sessions ADD COLUMN selected_gst_report_id VARCHAR(100) NULL"))
                except Exception:
                    pass
            if "selected_nongst_report_id" not in columns:
                try:
                    conn.execute(text("ALTER TABLE upload_sessions ADD COLUMN selected_nongst_report_id VARCHAR(100) NULL"))
                except Exception:
                    pass
            if "mapping_snapshot" not in columns:
                try:
                    conn.execute(text("ALTER TABLE upload_sessions ADD COLUMN mapping_snapshot TEXT NULL"))
                except Exception:
                    pass

    # 5. Check expense_records table additional columns
    if "expense_records" in inspector.get_table_names():
        columns = [col["name"] for col in inspector.get_columns("expense_records")]
        with engine.begin() as conn:
            if "error_code" not in columns:
                try:
                    conn.execute(text("ALTER TABLE expense_records ADD COLUMN error_code VARCHAR(100) NULL"))
                except Exception:
                    pass
            if "created_at" not in columns:
                try:
                    conn.execute(text("ALTER TABLE expense_records ADD COLUMN created_at DATETIME NULL"))
                except Exception:
                    pass
            if "updated_at" not in columns:
                try:
                    conn.execute(text("ALTER TABLE expense_records ADD COLUMN updated_at DATETIME NULL"))
                except Exception:
                    pass
