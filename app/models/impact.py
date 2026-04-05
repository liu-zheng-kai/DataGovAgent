from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class BusinessImpact(Base):
    __tablename__ = 'business_impacts'
    __table_args__ = (
        Index('ix_impact_source_asset', 'source_asset_id'),
        Index('ix_impact_active', 'is_active'),
        Index('ix_impact_target_asset', 'impacted_asset_id'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_asset_id: Mapped[int] = mapped_column(ForeignKey('assets.id'), nullable=False, index=True)
    impacted_asset_id: Mapped[int] = mapped_column(ForeignKey('assets.id'), nullable=True, index=True)
    impacted_team_id: Mapped[int] = mapped_column(ForeignKey('teams.id'), nullable=True, index=True)
    impacted_domain_id: Mapped[int] = mapped_column(ForeignKey('business_domains.id'), nullable=True, index=True)
    impact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    impact_level: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    detected_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    source_asset = relationship('Asset', foreign_keys=[source_asset_id])
    impacted_asset = relationship('Asset', foreign_keys=[impacted_asset_id])
    impacted_team = relationship('Team')
    impacted_domain = relationship('BusinessDomain')
