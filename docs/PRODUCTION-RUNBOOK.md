# Aifya Production Runbook

## Current Production

- Public app: https://aifyamed.com
- API health: https://aifyamed.com/api/health
- Keycloak discovery: https://aifyamed.com/auth/realms/aifya/.well-known/openid-configuration
- Server app directory: `/root/Aifya`

## Monitoring

GitHub Actions runs `.github/workflows/production-healthcheck.yml` every 15 minutes.
It checks the web app, API health endpoint, and Keycloak realm discovery endpoint.

This is a basic availability monitor. Before wider clinical use, add external alerting
that pages a human by SMS/phone/WhatsApp when checks fail.

## Facility License Bootstrap

Use `.github/workflows/facility-license-bootstrap.yml` to issue or replace the
active license for a facility. The production pilot facility defaults to:

```sh
00000000-0000-0000-0000-000000000001
```

For client demos, run the workflow manually with `tier=enterprise` or
`tier=professional`. This updates backend entitlements and clears the license
cache so the UI and API agree.

## Backups

GitHub Actions runs `.github/workflows/production-backup.yml` daily at 00:00 UTC.
It creates compressed PostgreSQL custom-format dumps on the VPS:

```sh
/root/Aifya/backups/postgres/aifya_YYYYMMDDTHHMMSSZ.dump.gz
```

Retention is currently 14 days on the same server.

When `BACKUP_RCLONE_CONFIG_B64` and `BACKUP_ENCRYPTION_PASSPHRASE` are configured
in GitHub Actions secrets, the backup workflow also encrypts the dump and uploads
the encrypted `.enc` copy plus checksum to an rclone remote such as Google Drive.

This is a minimum backup, not a complete disaster-recovery posture. Before handling
large volumes of real patient data, complete an off-server restore drill and make
sure at least two trusted people can access the encryption passphrase.

## Google Drive Off-Server Backup

Use Google Drive through `rclone`, with encryption applied before upload.

Required GitHub Actions secrets:

- `BACKUP_RCLONE_CONFIG_B64`: base64-encoded `rclone.conf` containing the Google Drive remote.
- `BACKUP_ENCRYPTION_PASSPHRASE`: strong passphrase used to encrypt backup files before upload.

Optional GitHub Actions variables:

- `BACKUP_RCLONE_REMOTE`: defaults to `gdrive:aifya-backups/postgres`.
- `BACKUP_REMOTE_RETENTION`: defaults to `30d`.

PowerShell helper to base64 encode a local rclone config:

```powershell
$config = "$env:APPDATA\rclone\rclone.conf"
[Convert]::ToBase64String([IO.File]::ReadAllBytes($config))
```

The uploaded files are encrypted with OpenSSL AES-256-CBC + PBKDF2:

```sh
aifya_YYYYMMDDTHHMMSSZ.dump.gz.enc
aifya_YYYYMMDDTHHMMSSZ.dump.gz.enc.sha256
```

## Manual Backup

Run the **Production Backup** workflow manually from GitHub Actions, or SSH to the
server and run:

```sh
cd /root/Aifya
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
postgres_user="$(sed -n 's/^POSTGRES_USER=//p' .env | tail -n 1)"
postgres_password="$(sed -n 's/^POSTGRES_PASSWORD=//p' .env | tail -n 1)"
postgres_db="$(sed -n 's/^POSTGRES_DB=//p' .env | tail -n 1)"
postgres_user="${postgres_user:-aifya_user}"
postgres_db="${postgres_db:-aifya}"
backup_file="/root/Aifya/backups/postgres/aifya_$(date -u +%Y%m%dT%H%M%SZ).dump.gz"
mkdir -p /root/Aifya/backups/postgres
$COMPOSE exec -T -u postgres -e PGPASSWORD="$postgres_password" postgres pg_dump \
  -U "$postgres_user" -d "$postgres_db" --format=custom --no-owner --no-acl \
  | gzip -c > "$backup_file"
gzip -t "$backup_file"
sha256sum "$backup_file" > "$backup_file.sha256"
```

## Restore Drill

Do not run this casually on production. It replaces the live database.

If restoring from Google Drive, first copy the encrypted backup back to the VPS
and decrypt it:

```sh
backup_file_enc="/root/Aifya/backups/postgres/REPLACE_WITH_BACKUP.dump.gz.enc"
backup_file="${backup_file_enc%.enc}"
openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 -md sha256 \
  -pass env:BACKUP_ENCRYPTION_PASSPHRASE \
  -in "$backup_file_enc" \
  -out "$backup_file"
gzip -t "$backup_file"
```

```sh
cd /root/Aifya
COMPOSE="docker compose -f docker-compose.yml -f docker-compose.prod.yml"
backup_file="/root/Aifya/backups/postgres/REPLACE_WITH_BACKUP.dump.gz"
postgres_user="$(sed -n 's/^POSTGRES_USER=//p' .env | tail -n 1)"
postgres_password="$(sed -n 's/^POSTGRES_PASSWORD=//p' .env | tail -n 1)"
postgres_db="$(sed -n 's/^POSTGRES_DB=//p' .env | tail -n 1)"
postgres_user="${postgres_user:-aifya_user}"
postgres_db="${postgres_db:-aifya}"

$COMPOSE stop api-gateway billing-service sync-service
$COMPOSE exec -T -u postgres -e PGPASSWORD="$postgres_password" postgres psql \
  -U "$postgres_user" -d postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '$postgres_db';"
$COMPOSE exec -T -u postgres -e PGPASSWORD="$postgres_password" postgres dropdb \
  -U "$postgres_user" --if-exists "$postgres_db"
$COMPOSE exec -T -u postgres -e PGPASSWORD="$postgres_password" postgres createdb \
  -U "$postgres_user" "$postgres_db"
gunzip -c "$backup_file" | $COMPOSE exec -T -u postgres -e PGPASSWORD="$postgres_password" postgres pg_restore \
  -U "$postgres_user" -d "$postgres_db" --no-owner --no-acl
$COMPOSE up -d postgres redis keycloak api-gateway billing-service sync-service
```

After restore, verify:

```sh
curl -fsS http://localhost:8000/api/health
curl -fsS http://localhost:8080/realms/aifya/.well-known/openid-configuration
```
