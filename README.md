# Hackathon Platform

Three FastAPI microservices on Amazon EKS: teams, submissions and judging.
Users sign in with Amazon Cognito; data lives in RDS PostgreSQL and S3.

```
team-service/         /teams        create, join and leave teams
submission-service/   /submissions  upload a team's project file to S3
judging-service/      /judging      judges score submissions; leaderboard
k8s/                  Deployment + Service per service, shared ConfigMap
docs/INTEGRATION.md   ports, routes, env vars and probes for the infra side
docker-compose.yml    run all three locally
```

## How the pieces fit

- Every route except `/health`, `/ready` and `/metrics` needs a Cognito **access token**:
  `Authorization: Bearer <token>`.
- Roles come from Cognito groups: `participants` create teams and submit; `judges` score.
- Users are identified by the token's `sub` claim.
- Services call each other inside the cluster and forward the caller's token:
  submission-service asks team-service for the caller's team, and
  judging-service asks submission-service whether a submission exists.
- Each service creates its own tables on startup (`teams`, `team_members`, `submissions`, `scores`).

## Run locally (Mac)

Needs Docker Desktop and your AWS CLI login (`aws sts get-caller-identity` works).

```bash
docker compose up --build
```

Get a test token (the test users already exist in the pool):

```bash
TOKEN=$(aws cognito-idp initiate-auth --region ap-south-1 \
  --client-id b56eo5k1q1ffcpsto6jrkj7ov --auth-flow USER_PASSWORD_AUTH \
  --auth-parameters USERNAME=participant1@test.com,PASSWORD='<test password>' \
  --query 'AuthenticationResult.AccessToken' --output text)

curl -X POST localhost:8001/teams -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"name":"Rockets"}'
curl -X POST localhost:8002/submissions -H "Authorization: Bearer $TOKEN" \
  -F title="Rocket App" -F file=@deck.pdf
```

Interactive API docs: `http://localhost:8001/docs`, `:8002/docs`, `:8003/docs`.

## Tests

The tests use a real PostgreSQL and locally signed tokens; S3 is mocked.

```bash
cd team-service
pip install -r requirements-dev.txt
DB_HOST=localhost DB_PORT=5432 DB_USER=postgres DB_PASSWORD=localdev DB_NAME=postgres pytest -q
```

Start the database first with `docker compose up -d postgres`.

## Build images

```bash
docker build --platform linux/amd64 -t team-service ./team-service
```

The EKS nodes are x86, so always build for `linux/amd64`. GitHub Actions builds the images used for deploys.
