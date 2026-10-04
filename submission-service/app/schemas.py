from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SubmissionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    team_id: int
    title: str
    description: str
    repo_url: str
    filename: str
    content_type: str
    size_bytes: int
    submitted_by: str
    created_at: datetime


class DownloadOut(BaseModel):
    url: str
    expires_in: int
