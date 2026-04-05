from sqlalchemy import Date, DateTime, Integer, JSON, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class DailySummaryReport(Base):
    __tablename__ = 'daily_summary_reports'
    __table_args__ = (
        UniqueConstraint('report_date', name='uq_daily_report_date'),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_date: Mapped[Date] = mapped_column(Date, nullable=False, index=True)
    summary_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    generated_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
