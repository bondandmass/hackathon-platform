from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .core.db import Base


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Score(Base):
    __tablename__ = "scores"
    __table_args__ = (UniqueConstraint("submission_id", "judge_sub", name="uq_one_score_per_judge"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    submission_id: Mapped[int] = mapped_column(Integer, index=True)
    team_id: Mapped[int] = mapped_column(Integer, index=True)
    submission_title: Mapped[str] = mapped_column(String(200))
    judge_sub: Mapped[str] = mapped_column(String(64))
    innovation: Mapped[int] = mapped_column(Integer)
    technical: Mapped[int] = mapped_column(Integer)
    impact: Mapped[int] = mapped_column(Integer)
    presentation: Mapped[int] = mapped_column(Integer)
    total: Mapped[float] = mapped_column(Float)
    comment: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)
