import os
import re
import uuid

from botocore.exceptions import BotoCoreError, ClientError
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from . import storage
from .core.auth import User, get_current_user, require_group
from .core.clients import get_json
from .core.db import get_db
from .models import Submission
from .schemas import DownloadOut, SubmissionOut

TEAM_SERVICE_URL = os.getenv("TEAM_SERVICE_URL", "http://team-service.hackathon.svc.cluster.local").rstrip("/")
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))

router = APIRouter(prefix="/submissions", tags=["submissions"])
participant = require_group("participants")


def caller_team_id(user: User) -> int | None:
    """Ask team-service which team the caller is in."""
    team = get_json(f"{TEAM_SERVICE_URL}/teams/me", user.token)
    return team["id"] if team else None


def _submission_or_404(db: Session, submission_id: int) -> Submission:
    sub = db.get(Submission, submission_id)
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")
    return sub


def _check_can_view(user: User, sub: Submission) -> None:
    if user.is_judge:
        return
    if caller_team_id(user) != sub.team_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only judges or the submitting team can view this")


def _safe_filename(name: str) -> str:
    base = os.path.basename(name or "upload")
    return re.sub(r"[^A-Za-z0-9._-]", "_", base)[:120] or "upload"


@router.post("", response_model=SubmissionOut, status_code=status.HTTP_201_CREATED)
def create_submission(
    title: str = Form(min_length=2, max_length=200),
    description: str = Form(default="", max_length=5000),
    repo_url: str = Form(default="", max_length=500),
    file: UploadFile = File(...),
    user: User = Depends(participant),
    db: Session = Depends(get_db),
):
    """Upload the caller's team submission (multipart form). One per team."""
    team_id = caller_team_id(user)
    if team_id is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Join or create a team before submitting")
    if db.scalar(select(Submission).where(Submission.team_id == team_id)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Your team already has a submission; delete it to resubmit")
    size = file.size or 0
    if size == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is empty")
    if size > MAX_UPLOAD_MB * 1024 * 1024:
        raise HTTPException(413, f"File larger than {MAX_UPLOAD_MB} MB")

    filename = _safe_filename(file.filename)
    content_type = file.content_type or "application/octet-stream"
    key = f"submissions/team-{team_id}/{uuid.uuid4().hex}-{filename}"
    try:
        storage.upload(file.file, key, content_type)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not store file") from exc

    sub = Submission(
        team_id=team_id, title=title, description=description, repo_url=repo_url, s3_key=key,
        filename=filename, content_type=content_type, size_bytes=size, submitted_by=user.sub,
    )
    db.add(sub)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        storage.delete(key)
        raise HTTPException(status.HTTP_409_CONFLICT, "Your team already has a submission")
    db.refresh(sub)
    return sub


@router.get("", response_model=list[SubmissionOut])
def list_submissions(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Judges see every submission; participants see their own team's."""
    query = select(Submission).order_by(Submission.id)
    if not user.is_judge:
        team_id = caller_team_id(user)
        if team_id is None:
            return []
        query = query.where(Submission.team_id == team_id)
    return db.scalars(query).all()


@router.get("/{submission_id}", response_model=SubmissionOut)
def get_submission(submission_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    sub = _submission_or_404(db, submission_id)
    _check_can_view(user, sub)
    return sub


@router.get("/{submission_id}/download", response_model=DownloadOut)
def download_submission(submission_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """A short-lived S3 link to the submitted file."""
    sub = _submission_or_404(db, submission_id)
    _check_can_view(user, sub)
    return DownloadOut(url=storage.download_url(sub.s3_key, sub.filename), expires_in=storage.URL_EXPIRY_SECONDS)


@router.delete("/{submission_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_submission(submission_id: int, user: User = Depends(participant), db: Session = Depends(get_db)):
    """The submitting team withdraws its submission."""
    sub = _submission_or_404(db, submission_id)
    if caller_team_id(user) != sub.team_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the submitting team can delete this")
    try:
        storage.delete(sub.s3_key)
    except (BotoCoreError, ClientError) as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not delete file") from exc
    db.delete(sub)
    db.commit()
