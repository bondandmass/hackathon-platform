import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .core.auth import User, get_current_user, require_group
from .core.db import get_db
from .models import Team, TeamMember
from .schemas import TeamCreate, TeamOut, TeamSummary

MAX_TEAM_SIZE = int(os.getenv("MAX_TEAM_SIZE", "4"))

router = APIRouter(prefix="/teams", tags=["teams"])
participant = require_group("participants")


def _team_or_404(db: Session, team_id: int) -> Team:
    team = db.get(Team, team_id)
    if team is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Team not found")
    return team


def _membership(db: Session, user_sub: str) -> TeamMember | None:
    return db.scalar(select(TeamMember).where(TeamMember.user_sub == user_sub))


@router.post("", response_model=TeamOut, status_code=status.HTTP_201_CREATED)
def create_team(body: TeamCreate, user: User = Depends(participant), db: Session = Depends(get_db)):
    """Create a team. The creator becomes its leader."""
    if _membership(db, user.sub):
        raise HTTPException(status.HTTP_409_CONFLICT, "You are already in a team")
    team = Team(name=body.name.strip(), description=body.description, created_by=user.sub)
    team.members.append(TeamMember(user_sub=user.sub, role="leader"))
    db.add(team)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Team name taken, or you are already in a team")
    db.refresh(team)
    return team


@router.get("", response_model=list[TeamSummary])
def list_teams(_: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """All teams with their member counts."""
    rows = db.execute(
        select(Team, func.count(TeamMember.user_sub))
        .outerjoin(TeamMember)
        .group_by(Team.id)
        .order_by(Team.id)
    ).all()
    return [
        TeamSummary(id=t.id, name=t.name, description=t.description, member_count=n, created_at=t.created_at)
        for t, n in rows
    ]


@router.get("/me", response_model=TeamOut)
def my_team(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """The caller's team."""
    membership = _membership(db, user.sub)
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You are not in a team")
    return membership.team


@router.get("/{team_id}", response_model=TeamOut)
def get_team(team_id: int, _: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return _team_or_404(db, team_id)


@router.post("/{team_id}/join", response_model=TeamOut)
def join_team(team_id: int, user: User = Depends(participant), db: Session = Depends(get_db)):
    team = _team_or_404(db, team_id)
    if _membership(db, user.sub):
        raise HTTPException(status.HTTP_409_CONFLICT, "You are already in a team")
    if len(team.members) >= MAX_TEAM_SIZE:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Team is full ({MAX_TEAM_SIZE} members)")
    team.members.append(TeamMember(user_sub=user.sub, role="member"))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "You are already in a team")
    db.refresh(team)
    return team


@router.post("/{team_id}/leave", status_code=status.HTTP_204_NO_CONTENT)
def leave_team(team_id: int, user: User = Depends(participant), db: Session = Depends(get_db)):
    """Leave a team. The last member leaving deletes it; a leaving leader hands over to the longest-standing member."""
    team = _team_or_404(db, team_id)
    me = next((m for m in team.members if m.user_sub == user.sub), None)
    if me is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "You are not in this team")
    remaining = [m for m in team.members if m.user_sub != user.sub]
    if not remaining:
        db.delete(team)
    else:
        team.members.remove(me)
        if me.role == "leader":
            remaining[0].role = "leader"
    db.commit()
