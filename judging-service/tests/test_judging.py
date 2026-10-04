import pytest

from app import routes
from app.scoring import weighted_total

from .conftest import bearer

J1 = bearer(sub="judge-1", groups=("judges",))
J2 = bearer(sub="judge-2", groups=("judges",))
ALICE = bearer(sub="alice")
SUBMISSIONS = {1: {"id": 1, "team_id": 10, "title": "Rocket"}, 2: {"id": 2, "team_id": 20, "title": "Comet"}}


@pytest.fixture(autouse=True)
def fake_submissions(monkeypatch):
    monkeypatch.setattr(routes, "get_json", lambda url, token: SUBMISSIONS.get(int(url.rsplit("/", 1)[1])))


def _score(client, headers, sid, v, comment=""):
    body = {"submission_id": sid, "innovation": v, "technical": v, "impact": v, "presentation": v, "comment": comment}
    return client.post("/judging/scores", json=body, headers=headers)


def test_weighted_total():
    assert weighted_total({"innovation": 10, "technical": 10, "impact": 10, "presentation": 10}) == 10.0
    assert weighted_total({"innovation": 8, "technical": 6, "impact": 4, "presentation": 2}) == 5.5


def test_health(client):
    assert client.get("/health").json()["service"] == "judging-service"


def test_only_judges_score(client):
    assert _score(client, ALICE, 1, 7).status_code == 403
    assert _score(client, J1, 99, 7).status_code == 404
    bad = client.post("/judging/scores", json={"submission_id": 1, "innovation": 11, "technical": 1, "impact": 1, "presentation": 1}, headers=J1)
    assert bad.status_code == 422
    assert client.get("/judging/scores", headers=ALICE).status_code == 403


def test_rescoring_updates(client):
    first = _score(client, J1, 1, 6)
    assert first.status_code == 201 and first.json()["total"] == 6.0
    second = _score(client, J1, 1, 9, "better")
    assert second.status_code == 200 and second.json()["id"] == first.json()["id"] and second.json()["total"] == 9.0
    assert len(client.get("/judging/scores?submission_id=1", headers=J2).json()) == 1


def test_leaderboard(client):
    _score(client, J1, 1, 6)
    _score(client, J2, 1, 8)
    _score(client, J1, 2, 9)
    board = client.get("/judging/leaderboard", headers=ALICE).json()
    assert [(e["rank"], e["title"], e["average_total"], e["judges"]) for e in board] == [
        (1, "Comet", 9.0, 1),
        (2, "Rocket", 7.0, 2),
    ]
    assert "judge_sub" not in board[0]
    assert client.get("/judging/criteria", headers=ALICE).json()["weights"]["innovation"] == 0.3
