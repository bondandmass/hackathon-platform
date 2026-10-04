import boto3
import pytest
from moto import mock_aws

from app import routes, storage

from .conftest import bearer

ALICE = bearer(sub="alice")          # team 1
CAROL = bearer(sub="carol")          # team 2
DAVE = bearer(sub="dave")            # no team
JUDGE = bearer(sub="judge", groups=("judges",))
TEAMS = {"alice": 1, "carol": 2}


@pytest.fixture(autouse=True)
def aws(monkeypatch):
    monkeypatch.setattr(routes, "caller_team_id", lambda user: TEAMS.get(user.sub))
    with mock_aws():
        storage.s3.cache_clear()
        boto3.client("s3", region_name="ap-south-1").create_bucket(
            Bucket="test-bucket", CreateBucketConfiguration={"LocationConstraint": "ap-south-1"}
        )
        yield
        storage.s3.cache_clear()


def _upload(client, headers, title="Demo"):
    return client.post(
        "/submissions",
        data={"title": title, "description": "desc", "repo_url": "https://github.com/x/y"},
        files={"file": ("my deck.pdf", b"%PDF-1.4 content", "application/pdf")},
        headers=headers,
    )


def _keys():
    resp = boto3.client("s3", region_name="ap-south-1").list_objects_v2(Bucket="test-bucket")
    return [o["Key"] for o in resp.get("Contents", [])]


def test_health(client):
    assert client.get("/health").json()["service"] == "submission-service"


def test_upload_lists_and_downloads(client):
    r = _upload(client, ALICE)
    assert r.status_code == 201, r.text
    sub = r.json()
    assert sub["team_id"] == 1 and sub["filename"] == "my_deck.pdf" and sub["size_bytes"] == 16
    assert len(_keys()) == 1 and _keys()[0].startswith("submissions/team-1/")

    assert _upload(client, ALICE).status_code == 409           # one per team
    assert [s["id"] for s in client.get("/submissions", headers=ALICE).json()] == [sub["id"]]
    assert client.get("/submissions", headers=CAROL).json() == []
    assert len(client.get("/submissions", headers=JUDGE).json()) == 1

    assert client.get(f"/submissions/{sub['id']}", headers=JUDGE).status_code == 200
    assert client.get(f"/submissions/{sub['id']}", headers=CAROL).status_code == 403
    dl = client.get(f"/submissions/{sub['id']}/download", headers=ALICE).json()
    assert "X-Amz-Signature" in dl["url"] and dl["expires_in"] == 900


def test_rules(client):
    assert _upload(client, DAVE).status_code == 409              # not in a team
    assert _upload(client, JUDGE).status_code == 403             # judges cannot submit
    empty = client.post("/submissions", data={"title": "x1"}, files={"file": ("a.txt", b"", "text/plain")}, headers=ALICE)
    assert empty.status_code == 400
    assert client.get("/submissions/999", headers=JUDGE).status_code == 404


def test_delete(client):
    sub = _upload(client, ALICE).json()
    assert client.delete(f"/submissions/{sub['id']}", headers=CAROL).status_code == 403
    assert client.delete(f"/submissions/{sub['id']}", headers=ALICE).status_code == 204
    assert _keys() == []
    assert _upload(client, ALICE).status_code == 201             # can resubmit after deleting
