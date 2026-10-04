import os

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .core.auth import User, get_current_user, require_group
from .core.clients import get_json
from .core.db import get_db
from .models import Score
from .schemas import LeaderboardEntry, ScoreIn, ScoreOut
from .scoring import CRITERIA, WEIGHTS, rank, weighted_total

SUBMISSION_SERVICE_URL = os.getenv(
    "SUBMISSION_SERVICE_URL", "http://submission-service.hackathon.svc.cluster.local"
).rstrip("/")

router = APIRouter(prefix="/judging", tags=["judging"])
judge = require_group("judges")


@router.post("/scores", response_model=ScoreOut)
def submit_score(body: ScoreIn, response: Response, user: User = Depends(judge), db: Session = Depends(get_db)):
    """Score a submission (judges only). Scoring the same submission again updates your score."""
    submission = get_json(f"{SUBMISSION_SERVICE_URL}/submissions/{body.submission_id}", user.token)
    if submission is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Submission not found")

    values = {c: getattr(body, c) for c in CRITERIA}
    score = db.scalar(
        select(Score).where(Score.submission_id == body.submission_id, Score.judge_sub == user.sub)
    )
    if score is None:
        score = Score(submission_id=body.submission_id, judge_sub=user.sub)
        db.add(score)
        response.status_code = status.HTTP_201_CREATED
    score.team_id = submission["team_id"]
    score.submission_title = submission["title"]
    for c, v in values.items():
        setattr(score, c, v)
    score.total = weighted_total(values)
    score.comment = body.comment
    db.commit()
    db.refresh(score)
    return score


@router.get("/scores", response_model=list[ScoreOut])
def list_scores(
    submission_id: int | None = Query(default=None),
    _: User = Depends(judge),
    db: Session = Depends(get_db),
):
    """All scores (judges only), optionally for one submission."""
    query = select(Score).order_by(Score.submission_id, Score.id)
    if submission_id is not None:
        query = query.where(Score.submission_id == submission_id)
    return db.scalars(query).all()


@router.get("/leaderboard", response_model=list[LeaderboardEntry])
def leaderboard(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Ranked submissions by average weighted score. Individual judges are not shown."""
    return rank(db.scalars(select(Score)).all())


@router.get("/criteria")
def criteria(_: User = Depends(get_current_user)) -> dict:
    """Scoring criteria and their weights."""
    return {"scale": [1, 10], "weights": WEIGHTS}
