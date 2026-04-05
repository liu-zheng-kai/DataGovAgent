from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class AssetRuntimeStatus(Base):
    __tablename__ = 'asset_runtime_status'
    __table_args__ = (
        UniqueConstraint('asset_id', name='uq_runtime_asset'),
        Index('ix_runtime_status_status', 'status'),
        Index('ix_runtime_status_delay', 'delay_minutes'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey('assets.id'), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    delay_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sla_risk_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=True)
    last_run_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    last_success_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    last_failure_at: Mapped[DateTime] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    asset = relationship('Asset')


class RuntimeEvent(Base):
    __tablename__ = 'runtime_events'
    __table_args__ = (
        Index('ix_runtime_events_time', 'occurred_at'),
        Index('ix_runtime_events_status', 'status'),
        Index('ix_runtime_events_asset', 'asset_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey('assets.id'), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    occurred_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(128), nullable=True)
    error_code: Mapped[str] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)
    details_json: Mapped[dict] = mapped_column(JSON, nullable=True)

    asset = relationship('Asset')


class DomainHealthSnapshot(Base):
    __tablename__ = 'domain_health_snapshots'
    __table_args__ = (
        Index('ix_domain_health_domain_time', 'domain_id', 'observed_at'),
        Index('ix_domain_health_status', 'status'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    domain_id: Mapped[int] = mapped_column(ForeignKey('business_domains.id'), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=True)
    observed_at: Mapped[DateTime] = mapped_column(DateTime, nullable=False, index=True)

    domain = relationship('BusinessDomain')
