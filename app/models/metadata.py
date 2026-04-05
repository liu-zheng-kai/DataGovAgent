from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Asset(Base):
    __tablename__ = 'assets'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    qualified_name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    refresh_frequency: Mapped[str] = mapped_column(String(64), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    system_id: Mapped[int] = mapped_column(ForeignKey('systems.id'), nullable=False, index=True)
    domain_id: Mapped[int] = mapped_column(ForeignKey('business_domains.id'), nullable=False, index=True)
    asset_type_id: Mapped[int] = mapped_column(ForeignKey('asset_types.id'), nullable=False, index=True)
    owner_team_id: Mapped[int] = mapped_column(ForeignKey('teams.id'), nullable=True, index=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    system = relationship('System')
    domain = relationship('BusinessDomain')
    asset_type = relationship('AssetType')
    owner_team = relationship('Team')


class AssetField(Base):
    __tablename__ = 'asset_fields'
    __table_args__ = (
        UniqueConstraint('asset_id', 'name', name='uq_asset_field_name'),
        Index('ix_asset_fields_asset_id', 'asset_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey('assets.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    data_type: Mapped[str] = mapped_column(String(100), nullable=False)
    is_nullable: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    asset = relationship('Asset')


class AssetDependency(Base):
    __tablename__ = 'asset_dependencies'
    __table_args__ = (
        UniqueConstraint('upstream_asset_id', 'downstream_asset_id', 'dependency_type_id', name='uq_dependency_path'),
        Index('ix_dep_upstream', 'upstream_asset_id'),
        Index('ix_dep_downstream', 'downstream_asset_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    upstream_asset_id: Mapped[int] = mapped_column(ForeignKey('assets.id'), nullable=False)
    downstream_asset_id: Mapped[int] = mapped_column(ForeignKey('assets.id'), nullable=False)
    dependency_type_id: Mapped[int] = mapped_column(ForeignKey('dependency_types.id'), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    upstream_asset = relationship('Asset', foreign_keys=[upstream_asset_id])
    downstream_asset = relationship('Asset', foreign_keys=[downstream_asset_id])
    dependency_type = relationship('DependencyType')


class SlaDefinition(Base):
    __tablename__ = 'sla_definitions'
    __table_args__ = (
        UniqueConstraint('asset_id', name='uq_sla_asset'),
        CheckConstraint('warning_after_minutes <= breach_after_minutes', name='ck_sla_warning_breach'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey('assets.id'), nullable=False, index=True)
    expected_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    warning_after_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    breach_after_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default='UTC', nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    asset = relationship('Asset')
