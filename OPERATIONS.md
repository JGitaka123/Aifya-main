# Aifya — Operations Guide

This document describes how the system is ACTUALLY deployed today:
a single-host **docker compose** stack (Next.js web + FastAPI api-gateway +
PostgreSQL/TimescaleDB + Keycloak + Redis + MinIO + Qdrant + the scribe and
knowledge AI services + Celery worker/beat), deployed over SSH by
`.github/workflows/deploy.yml` on every push to `main`.

> K3s, Traefik, Prometheus/Grafana/Loki/Tempo and Vault are mentioned in
> older docs but are NOT part of the current deployment. Do not follow any
> runbook that references them.

## 1. Deploy

Deploys are automatic: merging/pushing to `main` triggers
`.github/workflows/deploy.yml`, which

1. runs a compose config validation,
2. rsyncs the compose files + `services/api-gateway` to the server,
3. builds and restarts `keycloak` and `api-gateway`
   (`docker compose -f docker-compose.yml -f docker-compose.prod.yml`),
4. stamps/upgrades the database with `alembic upgrade head`,
5. rebuilds and restarts the web app under pm2.

Manual deploy from the server:

```bash
cd /root/Aifya
export COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
git pull                                  # or rsync from CI artifact
$COMPOSE build api-gateway
$COMPOSE up -d --force-recreate api-gateway
$COMPOSE run --rm api-gateway alembic upgrade head
```

**Approval gate (C-3):** the deploy job runs in the GitHub `production`
environment (see `.github/workflows/deploy.yml`). To activate the manual
approval gate, a repo admin must add a **required reviewer** to that
environment:

> GitHub → repo **Settings → Environments → `production` → Required
> reviewers** → add the release approver(s), then save.

Until a reviewer is configured the environment imposes no gate and every
push to `main` reaches production and runs migrations unattended — treat
merges to `main` as production deploys. This is a go-live checklist item.

## 2. Rollback

Application code:

```bash
cd /root/Aifya
git log --oneline -10          # find the last good commit
git checkout <good-sha>
$COMPOSE build api-gateway && $COMPOSE up -d --force-recreate api-gateway
```

Database: every alembic revision implements `downgrade()`:

```bash
$COMPOSE run --rm api-gateway alembic downgrade -1
```

Only downgrade immediately after a bad upgrade and before meaningful data
has been written. If in doubt, restore from backup instead (see below) —
never downgrade a database that has hours of clinical data on the new
schema without a plan for that data.

## 3. Backups

`scripts/backup-db.sh` produces a gzip-compressed `pg_dump` with an
integrity check (gzip test + pg_dump completion footer) and prunes dumps
older than 14 days.

Install the nightly cron on the server:

```bash
sudo crontab -e
# 02:15 nightly, log to /var/log/aifya-backup.log
15 2 * * * cd /root/Aifya && ./scripts/backup-db.sh >> /var/log/aifya-backup.log 2>&1
```

Copy dumps OFF the host (object storage, another machine) — a backup on
the same disk as the database does not survive a disk failure:

```bash
# example: sync to another host
rsync -az /var/backups/aifya/ backup-host:/srv/aifya-backups/
```

Also back up (lower cadence is acceptable):
- MinIO data volume (`minio-data`) — uploaded documents/audio
- Keycloak realm export: `docker compose exec keycloak /opt/keycloak/bin/kc.sh export --realm aifya --file /tmp/realm.json`

## 4. Restore — TEST THIS QUARTERLY

An untested backup is not a backup. To restore (and to drill the restore):

```bash
cd /root/Aifya
./scripts/restore-db.sh /var/backups/aifya/aifya-YYYYMMDD-HHMMSS.sql.gz
```

The script stops the API, drops and recreates the database, loads the
dump, verifies the table count, and restarts the API. For a drill without
touching production data, restore into a scratch database:

```bash
gunzip -c dump.sql.gz | docker compose exec -T postgres \
  psql -U aifya_user -d postgres -c "CREATE DATABASE aifya_drill;" \
  && gunzip -c dump.sql.gz | docker compose exec -T postgres psql -U aifya_user -d aifya_drill
docker compose exec -T postgres psql -U aifya_user -d aifya_drill -c "SELECT count(*) FROM patients;"
docker compose exec -T postgres psql -U aifya_user -d aifya_drill -c "DROP DATABASE aifya_drill;" -d postgres
```

Record each drill (date, dump used, row counts, time-to-restore) in the
facility's ops log.

## 5. Health checks & monitoring

- API: `GET /api/health` (used by the compose healthcheck)
- Web: `GET /` behind pm2/nginx
- Keycloak: `GET /health/ready`
- Worker: `docker compose exec api-worker celery -A app.worker inspect ping`

**Error tracking (done):** Sentry is wired in the API — set `SENTRY_DSN`
(and optionally `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE`) in the
server `.env` to enable it. With no DSN it stays disabled.

**Still needed — external uptime monitoring.** Sentry catches errors the
app reports; it does NOT tell you the host is down. Point an external
checker at the two public endpoints from OUTSIDE the host so a total
outage still alerts:

- `GET https://<host>/api/health` — expect `200` and JSON `{"status":"ok"}`
- `GET https://<host>/` — web root, expect `200`

Any hosted checker works (UptimeRobot, Better Stack, Pingdom, or a
Prometheus blackbox-exporter probe if one is later added). Recommended:
60s interval, alert after 2 consecutive failures, notify the on-call
channel. This is a go-live checklist item below.

> Prometheus/Grafana/Loki are NOT deployed. Metrics dashboards remain a
> future task; the uptime check above is the minimum viable substitute.

## 6. Incident basics

1. `docker compose ps` — is anything restarting/unhealthy?
2. `docker compose logs --tail=200 api-gateway` (structured logs; look
   for `*.gl.post_failed`, `mpesa_payment_record_error`, 5xx tracebacks).
3. Database up? `docker compose exec postgres pg_isready -U aifya_user`
4. Disk full is the most common single-host failure:
   `df -h`, prune with `docker system prune -f` (never prune volumes).
5. M-Pesa payments not reflecting → check `mpesa_payment_unmatched`
   warnings (wrong BillRefNumber) and the `payments` table by receipt.
6. If the API is up but auth fails, check Keycloak container and clock
   drift (`date` on host vs container).

Escalation: restore service first (restart the affected container),
preserve logs (`docker compose logs > /tmp/incident-$(date +%s).log`),
investigate second.

## 7. Go-live checklist

- [ ] `.env` on the server: strong `SECRET_KEY`, real `DATABASE_URL`
      password, `CORS_ORIGINS`, `KEYCLOAK_URL`; `DEBUG` unset/false
- [ ] Keycloak: change the seeded `admin123`/`demo123` passwords, delete
      demo users, enforce password policy + 2FA for admin roles
- [ ] Create a NON-superuser PostgreSQL role for the app so tenant RLS
      actually applies (audit finding H-3): run
      `scripts/create-app-db-role.sh` on the server (creates a
      `NOSUPERUSER`/`NOBYPASSRLS` `aifya_app` role), then point
      `DATABASE_URL` at that role and verify RLS with a cross-facility
      read
- [ ] GitHub `production` environment has a **required reviewer** so
      deploys pause for approval (Settings → Environments → `production`;
      audit finding C-3)
- [ ] `MPESA_CALLBACK_IP_ALLOWLIST` set to Safaricom's published IPs
      (callback IP enforcement is ON by default — `MPESA_CALLBACK_IP_ENFORCE`)
- [ ] `FIELD_ENCRYPTION_KEY` set to an explicit, independently-rotatable
      key (employee PII is encrypted at rest; blank derives from
      `SECRET_KEY`) and its custody documented
- [ ] (Optional, DPA minimum-necessary) `PATIENT_READ_ROLES` set to
      restrict who may READ patient PII / FHIR resources — leave blank to
      keep reads open to all authenticated facility staff
- [ ] Firewall: only 80/443 (and SSH from admin IPs) exposed; Postgres
      5432 and internal service ports NOT reachable from the internet
- [ ] Nightly backup cron installed AND one restore drill completed
- [ ] External uptime check on `/api/health` + web root wired in
      (see §5) and `SENTRY_DSN` set for error tracking
- [ ] SHA e-claims submission runs in MOCK mode until `SHA_ECLAIMS_URL`/
      `SHA_ECLAIMS_API_KEY` are set; ClaimFlow pre-submission validation
      needs `CLAIMFLOW_VALIDATOR_URL` (else claims validate as
      UNAVAILABLE). Confirm the billing office's workflow accounts for
      whichever are not yet live
- [ ] Scribe module is not usable via platform login (separate JWT user
      store) — keep it disabled/hidden unless separately provisioned
- [ ] Train staff per role: reception, clinician, pharmacy, lab, admin
