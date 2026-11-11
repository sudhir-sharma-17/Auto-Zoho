from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# Import settings to get DATABASE_URL
from app.config.config import settings

# Sanitize DATABASE_URL (Render PostgreSQL uses postgres:// which SQLAlchemy 1.4/2.0 requires postgresql://)
db_url = settings.DATABASE_URL
if db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# For SQLite, check_same_thread is set to False for multithreaded requests.
connect_args = {}
if db_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    db_url,
    connect_args=connect_args
)

# Enable WAL mode for SQLite to support concurrent reading and writing
if db_url.startswith("sqlite"):
    from sqlalchemy import event
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.close()

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    """Dependency injector to yield DB sessions and close them upon request completion."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
