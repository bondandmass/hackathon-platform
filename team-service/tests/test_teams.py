from cryptography.hazmat.primitives.asymmetric import rsa

from .conftest import bearer

ALICE = bearer(sub="alice")
BOB = bearer(sub="bob")
JUDGE = bearer(sub="judge", groups=("judges",))


def test_health_and_ready(client):
    assert client.get("/health").json() == {"status": "ok", "service": "team-service"}
    assert client.get("/ready").status_code == 200


def test_metrics_exposed(client):
    client.get("/health")
    body = client.get("/metrics").text
    assert 'http_requests_total{method="GET",route="/health",service="team-service",status="200"}' in body


def test_auth_rejections(client):
    assert client.get("/teams").status_code == 401
    assert client.get("/teams", headers={"Authorization": "Bearer junk"}).status_code == 401
    assert client.get("/teams", headers=bearer(token_use="id")).status_code == 401
    assert client.get("/teams", headers=bearer(client_id="other")).status_code == 401
    assert client.get("/teams", headers=bearer(exp_in=-120)).status_code == 401
    forged = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert client.get("/teams", headers=bearer(key=forged)).status_code == 401


def test_create_join_leave_flow(client):
    r = client.post("/teams", json={"name": "Rockets", "description": "d"}, headers=ALICE)
    assert r.status_code == 201, r.text
    team = r.json()
    assert team["members"][0] == {**team["members"][0], "user_sub": "alice", "role": "leader"}

    assert client.post("/teams", json={"name": "Again"}, headers=ALICE).status_code == 409
    assert client.post("/teams", json={"name": "Rockets"}, headers=BOB).status_code == 409

    r = client.post(f"/teams/{team['id']}/join", headers=BOB)
    assert r.status_code == 200 and len(r.json()["members"]) == 2

    assert client.get("/teams/me", headers=BOB).json()["id"] == team["id"]
    listed = client.get("/teams", headers=JUDGE).json()
    assert listed[0]["member_count"] == 2

    assert client.post(f"/teams/{team['id']}/leave", headers=ALICE).status_code == 204
    members = client.get(f"/teams/{team['id']}", headers=BOB).json()["members"]
    assert members == [{**members[0], "user_sub": "bob", "role": "leader"}]

    assert client.post(f"/teams/{team['id']}/leave", headers=BOB).status_code == 204
    assert client.get(f"/teams/{team['id']}", headers=BOB).status_code == 404


def test_judges_cannot_create_or_join(client):
    assert client.post("/teams", json={"name": "Judges"}, headers=JUDGE).status_code == 403
    team = client.post("/teams", json={"name": "T1"}, headers=ALICE).json()
    assert client.post(f"/teams/{team['id']}/join", headers=JUDGE).status_code == 403


def test_team_size_limit(client):
    team = client.post("/teams", json={"name": "Full"}, headers=ALICE).json()
    for i in range(3):
        assert client.post(f"/teams/{team['id']}/join", headers=bearer(sub=f"u{i}")).status_code == 200
    assert client.post(f"/teams/{team['id']}/join", headers=BOB).status_code == 409


def test_me_without_team(client):
    assert client.get("/teams/me", headers=BOB).status_code == 404
