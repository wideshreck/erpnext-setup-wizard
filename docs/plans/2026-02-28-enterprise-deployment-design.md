# Enterprise Deployment Evolution — Design Document

**Date:** 2026-02-28
**Status:** Approved

## Goal

Evolve the ERPNext Setup Wizard from a localhost-only development tool into an enterprise-grade deployment system supporting three modes: local development, production server, and remote SSH deployment.

## Approach: Monolithic Refactor

Extend the existing wizard incrementally. Add a `deploy_mode` field to Config and branch logic within each step based on mode. No new plugin architecture or pipeline engine — the current step-based structure is sufficient for 3 modes.

---

## Deployment Modes

### 1. Local Development (existing)
- `127.0.0.1`, HTTP-only, `compose.noproxy.yaml`
- Auto-updates hosts file
- Completion banner: `http://site:port`

### 2. Production Server
- Real domain (`erp.example.com`), HTTPS via Traefik + Let's Encrypt
- `compose.erpnext.yaml` (traefik overlay)
- No hosts file modification — DNS assumed
- Completion banner: `https://domain`

### 3. Remote Server (SSH)
- Same as production, but all commands run via SSH on remote host
- Wizard runs locally, executes commands on remote server
- frappe_docker cloned on remote: `~/frappe_docker`
- `.env` and config files transferred via `scp`

---

## Config Dataclass Extension

```python
@dataclass
class Config:
    # Core (all modes)
    deploy_mode: str              # "local" | "production" | "remote"
    site_name: str
    erpnext_version: str
    db_type: str                  # "mariadb" | "postgres"
    db_password: str
    admin_password: str
    extra_apps: list[str]
    community_apps: list[CommunityApp]

    # Production + Remote
    domain: str                   # "" for local mode
    letsencrypt_email: str        # "" for local mode
    http_port: str                # only used in local mode

    # Remote SSH
    ssh_host: str                 # "" for non-remote
    ssh_user: str                 # "" for non-remote
    ssh_port: int                 # 22 default
    ssh_key_path: str             # "" = use ssh-agent/default

    # Optional: SMTP
    smtp_host: str                # "" = skip
    smtp_port: int                # 587 default
    smtp_user: str
    smtp_password: str
    smtp_use_tls: bool            # True default

    # Optional: Backup (S3-compatible)
    backup_enabled: bool          # False = skip
    backup_s3_endpoint: str
    backup_s3_bucket: str
    backup_s3_access_key: str
    backup_s3_secret_key: str
```

---

## SSH Execution Engine

**New module: `wizard/ssh.py`**

### Executor Pattern

Both local and remote execution share the same interface:

```python
class LocalExecutor:
    def run(self, cmd, capture=False) -> int | tuple[int, str, str]:
        # Delegates to existing utils.run()

    def upload(self, local_path, remote_path):
        # shutil.copy (local-to-local)

class SSHExecutor:
    def __init__(self, host, user, port=22, key_path=None): ...

    def run(self, cmd, capture=False) -> int | tuple[int, str, str]:
        # subprocess: ssh user@host -p port 'cmd'

    def upload(self, local_path, remote_path):
        # subprocess: scp -P port local_path user@host:remote_path

    def test_connection(self) -> bool:
        # ssh user@host "echo ok"
```

**No external dependencies** — uses system `ssh` and `scp` commands via `subprocess`.

Step functions receive an `executor` parameter:
```python
# Before: code = run(f"{COMPOSE_CMD} exec -T backend ...")
# After:  code = executor.run(f"{COMPOSE_CMD} exec -T backend ...")
```

### Prerequisites Check (Remote)

1. `ssh` command available locally
2. `scp` command available locally
3. Connection test: `ssh user@host "echo ok"`
4. Remote Docker: `ssh user@host "docker --version"`
5. Remote Docker Compose: `ssh user@host "docker compose version"`
6. Remote Git: `ssh user@host "git --version"`

---

## Docker Compose Configuration

### Dynamic COMPOSE_CMD

Replace hardcoded `COMPOSE_CMD` with `build_compose_cmd(cfg)`:

```python
def build_compose_cmd(cfg: Config) -> str:
    files = ["compose.yaml"]

    # Database
    if cfg.db_type == "mariadb":
        files.append("overrides/compose.mariadb.yaml")
    else:
        files.append("overrides/compose.postgres.yaml")

    # Redis (always)
    files.append("overrides/compose.redis.yaml")

    # Proxy
    if cfg.deploy_mode == "local":
        files.append("overrides/compose.noproxy.yaml")
    else:
        files.append("overrides/compose.erpnext.yaml")

    return "docker compose " + " ".join(f"-f {f}" for f in files)
```

### Env File by Mode

**Local mode (.env):**
```env
ERPNEXT_VERSION=v16.7.3
FRAPPE_VERSION=version-16
DB_PASSWORD=secret
FRAPPE_SITE_NAME_HEADER=mysite.localhost
HTTP_PUBLISH_PORT=8080
LETSENCRYPT_EMAIL=mail@example.com
```

**Production mode (.env):**
```env
ERPNEXT_VERSION=v16.7.3
FRAPPE_VERSION=version-16
DB_PASSWORD=secret
FRAPPE_SITE_NAME_HEADER=erp.example.com
TRAEFIK_DOMAIN=erp.example.com
LETSENCRYPT_EMAIL=admin@example.com
```

**Remote mode:** Same as production, transferred via `scp`.

### PostgreSQL Support

When `db_type == "postgres"`:
- Uses `overrides/compose.postgres.yaml`
- `bench new-site` gets `--db-type postgres` flag
- DB_PASSWORD used as postgres root password

---

## SMTP Configuration (Optional)

Asked during configure step for production/remote modes: "Configure email (SMTP)?"

If yes, collects: host, port (default 587), user, password, TLS (default yes).

Applied after site creation via bench:
```bash
bench --site {site} set-config mail_server {host}
bench --site {site} set-config mail_port {port}
bench --site {site} set-config mail_login {user}
bench --site {site} set-config mail_password {pass}
bench --site {site} set-config use_tls {1|0}
```

---

## Backup Configuration (Optional)

Asked during configure step for production/remote modes: "Configure S3 backup?"

If yes, collects: S3 endpoint, bucket, access key, secret key.

Applied via bench:
```bash
bench --site {site} set-config backup_bucket {bucket}
bench --site {site} set-config backup_region ""
bench --site {site} set-config backup_endpoint {endpoint}
bench --site {site} set-config backup_access_key {access_key}
bench --site {site} set-config backup_secret_key {secret_key}
```

---

## Unattended Mode

Two methods, both produce the same Config object:

### CLI Flags

```bash
erpnext-setup-wizard --mode production \
  --site-name erp.example.com \
  --version v16.7.3 \
  --db-type mariadb \
  --db-password secret \
  --admin-password admin \
  --domain erp.example.com \
  --letsencrypt-email admin@example.com \
  --apps hrms,payments \
  --smtp-host smtp.gmail.com \
  --smtp-port 587 \
  --smtp-user noreply@example.com \
  --smtp-password apppass \
  --backup-s3-endpoint https://s3.amazonaws.com \
  --backup-s3-bucket erp-backups \
  --backup-s3-access-key AKIA... \
  --backup-s3-secret-key secret
```

For remote mode, add:
```bash
  --ssh-host 192.168.1.100 \
  --ssh-user deploy \
  --ssh-port 22 \
  --ssh-key ~/.ssh/id_rsa
```

### Config File (YAML)

```bash
erpnext-setup-wizard --config deploy.yml
```

```yaml
mode: production
site_name: erp.example.com
erpnext_version: v16.7.3
db_type: mariadb
db_password: secret
admin_password: admin
domain: erp.example.com
letsencrypt_email: admin@example.com
extra_apps:
  - hrms
  - payments
smtp:
  host: smtp.gmail.com
  port: 587
  user: noreply@example.com
  password: apppass
  use_tls: true
backup:
  s3_endpoint: https://s3.amazonaws.com
  s3_bucket: erp-backups
  s3_access_key: AKIA...
  s3_secret_key: secret
ssh:
  host: 192.168.1.100
  user: deploy
  port: 22
  key_path: ~/.ssh/id_rsa
```

### New Module: `wizard/config_loader.py`

Parsing priority: CLI args > config file > interactive prompts.

- Uses `argparse` for CLI flags
- Uses `PyYAML` (new dependency) for config file
- If sufficient args provided, skips interactive prompts entirely
- Validates all fields with same validators as interactive mode

---

## Step-by-Step Flow Changes

### Step 1: Prerequisites

| Check | Local | Production | Remote |
|-------|-------|------------|--------|
| Docker | local | local | remote (SSH) |
| Docker Compose | local | local | remote (SSH) |
| Git | local | local | remote (SSH) |
| SSH client | - | - | local |
| SSH connection | - | - | test |
| Clone frappe_docker | local cwd | local cwd | remote ~/frappe_docker |

### Step 2: Configure

New prompt order:
1. Deploy mode (local/production/remote)
2. SSH details (remote only)
3. Site name
4. ERPNext version
5. Database type (MariaDB/PostgreSQL)
6. HTTP port (local only) / Domain + SSL email (production/remote)
7. Passwords (DB + admin)
8. Optional apps + community apps
9. SMTP config (optional, production/remote)
10. Backup config (optional, production/remote)
11. Summary table + confirmation

### Step 3: Env File

- Local: write `.env` in local frappe_docker dir
- Production: write `.env` in local frappe_docker dir
- Remote: write `.env` locally, `scp` to remote `~/frappe_docker/.env`

### Step 4: Docker

- Local/Production: `docker compose ... up -d` (local)
- Remote: `ssh user@host "cd ~/frappe_docker && docker compose ... up -d"`
- DB wait: 25s (local) / 35s (remote, network latency buffer)

### Step 5: Site

- `bench new-site` with `--db-type postgres` if applicable
- SMTP config via `bench set-config` (if configured)
- Backup config via `bench set-config` (if configured)
- Hosts file: only local mode
- Completion banner: `http://site:port` (local) / `https://domain` (production/remote)
- DNS reminder for production/remote modes

---

## i18n Updates

New keys needed across all 6 languages:

**Deploy mode:**
- `steps.configure.deploy_mode` — "Deployment mode"
- `steps.configure.deploy_local` — "Local development"
- `steps.configure.deploy_production` — "Production server"
- `steps.configure.deploy_remote` — "Remote server (SSH)"

**SSH:**
- `steps.configure.ssh_host` — "Server address"
- `steps.configure.ssh_user` — "SSH username"
- `steps.configure.ssh_port` — "SSH port"
- `steps.configure.ssh_key` — "SSH key path"
- `steps.prerequisites.checking_ssh` — "Checking SSH connection..."
- `steps.prerequisites.ssh_ok` — "SSH connection successful"
- `steps.prerequisites.ssh_failed` — "SSH connection failed"

**Database:**
- `steps.configure.db_type` — "Database type"

**Domain/SSL:**
- `steps.configure.domain` — "Domain name"
- `steps.configure.letsencrypt_email` — "Let's Encrypt email"

**SMTP:**
- `steps.configure.smtp_configure` — "Configure email (SMTP)?"
- `steps.configure.smtp_host` — "SMTP server"
- `steps.configure.smtp_port` — "SMTP port"
- `steps.configure.smtp_user` — "SMTP username"
- `steps.configure.smtp_password` — "SMTP password"

**Backup:**
- `steps.configure.backup_configure` — "Configure S3 backup?"
- `steps.configure.backup_s3_endpoint` — "S3 endpoint"
- `steps.configure.backup_s3_bucket` — "Bucket name"

**Site/completion:**
- `steps.site.dns_reminder` — "Make sure DNS points to your server"
- `steps.site.done_url_https` — "Your site is live at {url}"

---

## New Dependencies

- `PyYAML` — for config file parsing (unattended mode)
- No other new dependencies (SSH via subprocess)

---

## File Changes Summary

| File | Change |
|------|--------|
| `wizard/ssh.py` | **NEW** — SSHExecutor, LocalExecutor |
| `wizard/config_loader.py` | **NEW** — CLI args + YAML parsing |
| `wizard/steps/configure.py` | **MODIFY** — deploy mode, DB type, SSH, domain, SMTP, backup prompts |
| `wizard/steps/docker.py` | **MODIFY** — dynamic COMPOSE_CMD, executor pattern |
| `wizard/steps/env_file.py` | **MODIFY** — mode-aware .env generation, remote upload |
| `wizard/steps/prerequisites.py` | **MODIFY** — remote checks, SSH validation |
| `wizard/steps/site.py` | **MODIFY** — executor pattern, SMTP/backup config, conditional hosts |
| `wizard/utils.py` | **MODIFY** — extract LocalExecutor |
| `wizard/i18n/*.json` (x6) | **MODIFY** — ~25 new keys per language |
| `erpnext-setup-wizard.py` | **MODIFY** — argparse integration, config_loader |
| `pyproject.toml` | **MODIFY** — add PyYAML dependency |
