from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScoreIn(BaseModel):
    submission_id: int
    innovation: int = Field(ge=1, le=10)
    technical: int = Field(ge=1, le=10)
    impact: int = Field(ge=1, le=10)
    presentation: int = Field(ge=1, le=10)
    comment: str = Field(default="", max_length=2000)


class ScoreOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    submission_id: int
    team_id: int
    judge_sub: str
    innovation: int
    technical: int
    impact: int
    presentation: int
    total: float
    comment: str
    created_at: datetime
    updated_at: datetime


class LeaderboardEntry(BaseModel):
    rank: int
    submission_id: int
    team_id: int
    title: str
    judges: int
    average_total: float
    innovation: float
    technical: float
    impact: float
    presentation: float
