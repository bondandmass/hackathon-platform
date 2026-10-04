from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TeamCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    description: str = Field(default="", max_length=1000)


class MemberOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_sub: str
    role: str
    joined_at: datetime


class TeamSummary(BaseModel):
    id: int
    name: str
    description: str
    member_count: int
    created_at: datetime


class TeamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    description: str
    created_by: str
    created_at: datetime
    members: list[MemberOut]
