from collections.abc import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import settings


class Base(DeclarativeBase):
    pass


def _create_engine(url: str):
    return create_engine(
        url,
        pool_pre_ping=True,
        future=True,
    )


def _should_try_fallback() -> bool:
    return (
        settings.env.lower() == 'local'
        and settings.database_fallback_on_connect_error
        and settings.database_url.startswith('mysql')
        and bool(settings.database_fallback_url.strip())
    )


def _build_engine():
    primary_engine = _create_engine(settings.database_url)
    if not _should_try_fallback():
        return primary_engine

    try:
        with primary_engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        return primary_engine
    except OperationalError as exc:
        print(
            f'[DB] Primary database unavailable ({exc}). '
            f'Falling back to {settings.database_fallback_url}'
        )
        return _create_engine(settings.database_fallback_url)


engine = _build_engine()
SessionLocal = sessionmaker(
    bind=engine, autocommit=False, autoflush=False, expire_on_commit=False, class_=Session
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
