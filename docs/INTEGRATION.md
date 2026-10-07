# Integration contract (application side)

Everything below is implemented and tested; nothing is planned-only.

## 1. Code location

| Service | Folder | Dockerfile |
| --- | --- | --- |
| Team | `team-service/` | `team-service/Dockerfile` |
| Submission | `submission-service/` | `submission-service/Dockerfile` |
| Judging | `judging-service/` | `judging-service/Dockerfile` |

Kubernetes manifests: `k8s/`.

## 2–4. Container, port and start command

All three: base `python:3.12-slim`, run as non-root UID 10001, listen on `0.0.0.0:8000`.
Build from inside each folder: `docker build --platform linux/amd64 .`

Start command (same for all three, set as the image `CMD`):

```
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers --forwarded-allow-ips *
```

One worker per pod on purpose: scale with replicas (HPA), and `/metrics` stays accurate.

## 5. Health endpoints

| Path | Use | Response |
| --- | --- | --- |
| `GET /health` | liveness, startup, ALB health check | `200 {"status":"ok","service":"team-service"}` |
| `GET /ready` | readiness (checks the database) | `200 {"status":"ready","service":"..."}`, or `503 {"status":"not ready",...}` |

Neither needs a token. They sit at the root, not under `/teams` etc.: point the ALB health check at `/health`.

## 6. Prometheus metrics

`GET /metrics` on port 8000, no token. Already implemented. Pods carry
`prometheus.io/scrape: "true"`, `prometheus.io/port: "8000"`, `prometheus.io/path: /metrics`.

| Metric | Type | Labels |
| --- | --- | --- |
| `http_requests_total` | counter | service, method, route, status |
| `http_request_duration_seconds` | histogram | service, method, route |
| `http_requests_in_progress` | gauge | service |

`route` is the route template (`/teams/{team_id}`), never a raw path.

## 7. Environment variables

Common to all three:

| Variable | Required | Notes |
| --- | --- | --- |
| `DB_HOST` | yes | RDS endpoint |
| `DB_PORT` | no | default `5432` |
| `DB_NAME` | no | default `postgres` |
| `DB_USER` | yes | |
| `DB_PASSWORD` | yes | from Secret `hackathon-db` |
| `DB_SSLMODE` | no | default `require` (RDS forces SSL) |
| `AWS_REGION` | no | default `ap-south-1` |
| `COGNITO_REGION` | no | defaults to `AWS_REGION` |
| `COGNITO_USER_POOL_ID` | yes | |
| `COGNITO_APP_CLIENT_ID` | yes | |

Extra per service:

| Service | Variable | Required | Notes |
| --- | --- | --- | --- |
| Team | `MAX_TEAM_SIZE` | no | default `4` |
| Submission | `S3_BUCKET` | yes | |
| Submission | `TEAM_SERVICE_URL` | no | default `http://team-service.hackathon.svc.cluster.local` |
| Submission | `MAX_UPLOAD_MB` | no | default `20` |
| Judging | `SUBMISSION_SERVICE_URL` | no | default `http://submission-service.hackathon.svc.cluster.local` |

A missing required variable stops the service at startup with a clear error.
No AWS keys: S3 access comes from Pod Identity on service account `hackathon-app`.

## 8. Kubernetes manifests

| File | Contents |
| --- | --- |
| `k8s/configmap.yaml` | `hackathon-config`: all non-secret settings |
| `k8s/team-service.yaml` | Deployment + ClusterIP Service |
| `k8s/submission-service.yaml` | Deployment + ClusterIP Service |
| `k8s/judging-service.yaml` | Deployment + ClusterIP Service |
| `k8s/examples/db-secret.example.yaml` | shape of Secret `hackathon-db` (not applied) |

Each Deployment: namespace `hackathon`, service account `hackathon-app`, image
`588199412082.dkr.ecr.ap-south-1.amazonaws.com/hackathon/<service>:latest` (CI swaps in the SHA tag),
port 8000, startup/readiness/liveness probes, requests `100m` CPU / `128Mi`, limits `500m` CPU /
`256Mi` (`384Mi` for submission), non-root, read-only root filesystem with an `emptyDir` on `/tmp`.
Services: port `80` → `8000`, named `team-service`, `submission-service`, `judging-service`.

There is **no `replicas` field**, so HPA owns the count and `kubectl apply` won't reset it.
Ingress and HPA are not included.

Create the Secret before the first deploy:

```bash
kubectl create secret generic hackathon-db -n hackathon --from-literal=DB_PASSWORD='<rotated password>'
```

## 9. Routes

All need `Authorization: Bearer <Cognito access token>`.

**Team service**

| Method | Path | Who | Does |
| --- | --- | --- | --- |
| POST | `/teams` | participants | create a team (`{"name","description"}`); creator becomes leader |
| GET | `/teams` | any user | list teams with member counts |
| GET | `/teams/me` | any user | the caller's team (404 if none) |
| GET | `/teams/{team_id}` | any user | one team with members |
| POST | `/teams/{team_id}/join` | participants | join (max 4, one team per person) |
| POST | `/teams/{team_id}/leave` | participants | leave; last member out deletes the team |

**Submission service**

| Method | Path | Who | Does |
| --- | --- | --- | --- |
| POST | `/submissions` | participants | multipart upload: `title`, `description`, `repo_url`, `file`; one per team |
| GET | `/submissions` | any user | judges see all; participants see their team's |
| GET | `/submissions/{id}` | judges, own team | metadata |
| GET | `/submissions/{id}/download` | judges, own team | presigned S3 URL, valid 15 min |
| DELETE | `/submissions/{id}` | own team | withdraw (deletes the S3 file) |

**Judging service**

| Method | Path | Who | Does |
| --- | --- | --- | --- |
| POST | `/judging/scores` | judges | score 1–10 on innovation, technical, impact, presentation; re-posting updates |
| GET | `/judging/scores?submission_id=` | judges | all scores, optionally for one submission |
| GET | `/judging/leaderboard` | any user | ranked by average weighted score |
| GET | `/judging/criteria` | any user | weights: innovation 0.30, technical 0.30, impact 0.25, presentation 0.15 |

The prefixes `/teams`, `/submissions` and `/judging` are correct for the Ingress. Use `pathType: Prefix`
and do not strip the prefix; the apps expect the full path.

## 10. Frontend

| Item | Value |
| --- | --- |
| Folder | `frontend/` (static HTML, CSS and JS; no build step) |
| Image | `nginxinc/nginx-unprivileged`, non-root UID 101, port `8080`, `linux/amd64` |
| ECR repo | `hackathon/frontend` (create once before the first deploy) |
| Health | `GET /health` returns `200 {"status":"ok","service":"frontend"}` |
| Ingress | `/app` (Prefix) and `/` (Exact, public landing page) go to Service `frontend` port 80 |
| Manifest | `k8s/frontend.yaml`: 1 replica, 20m/32Mi requests, 200m/64Mi limits; no HPA needed |

The browser signs in directly with Cognito (`USER_PASSWORD_AUTH` on the app client) and calls the
APIs on the same ALB origin, so no CORS setup is needed.

```bash
aws ecr create-repository --repository-name hackathon/frontend --region ap-south-1
```
