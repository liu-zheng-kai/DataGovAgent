from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class SourceSyncState(Base):
    __tablename__ = 'source_sync_state'
    __table_args__ = (
        UniqueConstraint('source_name', name='uq_source_sync_state_name'),
        Index('ix_source_sync_state_status', 'last_status'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    scope_ref: Mapped[str] = mapped_column(String(255), nullable=True)
    last_status: Mapped[str] = mapped_column(String(32), nullable=False, default='IDLE')
    last_cursor: Mapped[str] = mapped_column(String(255), nullable=True)
    last_error: Mapped[str] = mapped_column(Text, nullable=True)
    record_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_started_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    last_succeeded_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    last_failed_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime,
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class IngestionJob(Base):
    __tablename__ = 'ingestion_jobs'
    __table_args__ = (
        Index('ix_ingestion_jobs_source', 'source_name'),
        Index('ix_ingestion_jobs_status', 'status'),
        Index('ix_ingestion_jobs_started', 'started_at'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False, default='metadata_sync')
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='RUNNING')
    scope_ref: Mapped[str] = mapped_column(String(255), nullable=True)
    sync_state_id: Mapped[int] = mapped_column(ForeignKey('source_sync_state.id'), nullable=True, index=True)
    records_scanned: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_written: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    finished_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    details_json: Mapped[dict] = mapped_column(JSON, nullable=True)

    sync_state = relationship('SourceSyncState')


class RawMetadataSnapshot(Base):
    __tablename__ = 'raw_metadata_snapshots'
    __table_args__ = (
        Index('ix_raw_metadata_source', 'source_name'),
        Index('ix_raw_metadata_entity', 'entity_type', 'entity_key'),
        Index('ix_raw_metadata_captured', 'captured_at'),
        Index('ix_raw_metadata_hash', 'snapshot_hash'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    sync_state_id: Mapped[int] = mapped_column(ForeignKey('source_sync_state.id'), nullable=True, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    observed_state: Mapped[str] = mapped_column(String(32), nullable=False, default='deployed')
    source_version: Mapped[str] = mapped_column(String(255), nullable=True)
    snapshot_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    payload_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    captured_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    sync_state = relationship('SourceSyncState')
