"""Database engine, sessions and safe table creation."""
import logging
import time
import zlib

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

log = logging.getLogger(__name__)


class Base(DeclarativeBase):
    pass


_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def get_engine() -> Engine:
    global _engine, _SessionLocal
    if _engine is None:
        s = get_settings()
        # URL.create escapes special characters (such as @) in the password.
        url = URL.create(
            "postgresql+psycopg",
            username=s.db_user,
            password=s.db_password,
            host=s.db_host,
            port=s.db_port,
            database=s.db_name,
        )
        _engine = create_engine(
            url,
            connect_args={"sslmode": s.db_sslmode, "connect_timeout": 5},
            pool_size=5,
            max_overflow=5,
            pool_pre_ping=True,
            pool_recycle=1800,
        )
        _SessionLocal = sessionmaker(bind=_engine, expire_on_commit=False)
    return _engine


def get_db():
    get_engine()
    db: Session = _SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db(service_name: str, attempts: int = 10, delay: float = 3.0) -> None:
    """Create this service's tables. An advisory lock stops replicas racing each other."""
    lock_id = zlib.crc32(service_name.encode())
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            engine = get_engine()
            with engine.begin() as conn:
                conn.execute(text("SELECT pg_advisory_xact_lock(:id)"), {"id": lock_id})
                Base.metadata.create_all(conn)
            log.info("database ready (attempt %d)", attempt)
            return
        except Exception as exc:  # noqa: BLE001 - retry on any connection error
            last_error = exc
            log.warning("database not ready (attempt %d/%d): %s", attempt, attempts, exc)
            time.sleep(delay)
    raise RuntimeError(f"database unavailable after {attempts} attempts") from last_error


def db_is_ready() -> bool:
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False
