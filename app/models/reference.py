from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class Team(Base):
    __tablename__ = 'teams'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    email: Mapped[str] = mapped_column(String(200), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)


class BusinessDomain(Base):
    __tablename__ = 'business_domains'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    criticality: Mapped[str] = mapped_column(String(32), default='MEDIUM', nullable=False)
    owner_team_id: Mapped[int] = mapped_column(ForeignKey('teams.id'), nullable=True, index=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)

    owner_team = relationship('Team')


class System(Base):
    __tablename__ = 'systems'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    system_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    environment: Mapped[str] = mapped_column(String(32), default='prod', nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)


class AssetType(Base):
    __tablename__ = 'asset_types'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)


class DependencyType(Base):
    __tablename__ = 'dependency_types'

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
