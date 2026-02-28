# ERPNext Setup Wizard

An interactive terminal wizard that sets up a production-ready [ERPNext](https://erpnext.com) instance using [frappe_docker](https://github.com/frappe/frappe_docker). One command, five guided steps, zero Docker expertise required.

```
███████╗██████╗ ██████╗ ███╗   ██╗███████╗██╗  ██╗████████╗
██╔════╝██╔══██╗██╔══██╗████╗  ██║██╔════╝╚██╗██╔╝╚══██╔══╝
█████╗  ██████╔╝██████╔╝██╔██╗ ██║█████╗   ╚███╔╝    ██║
██╔══╝  ██╔══██╗██╔═══╝ ██║╚██╗██║██╔══╝   ██╔██╗    ██║
███████╗██║  ██║██║     ██║ ╚████║███████╗██╔╝ ██╗   ██║
╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝   ╚═╝
```

## Features

- **3 deployment modes** — local development, production server (HTTPS), or remote server via SSH
- **Automatic SSL** — Traefik + Let's Encrypt for production and remote modes
- **Database choice** — MariaDB or PostgreSQL
- **Version selector** — fetches all stable ERPNext releases (v14+) from GitHub with autocomplete search
- **Optional Frappe apps** — install HRMS, Payments, Healthcare, Education, Lending, Webshop, Print Designer, or Wiki
- **Community apps** — discover and install apps from [awesome-frappe](https://github.com/gavindsouza/awesome-frappe)
- **SMTP configuration** — optional email sending setup for production deployments
- **S3 backup** — optional S3-compatible backup configuration
- **Unattended mode** — deploy from CLI flags or a YAML config file (CI/CD ready)
- **Multi-language** — English, Turkish, German, Spanish, French, Italian
- **Input validation** — site name format, port range, password confirmation, email format

## Prerequisites

- **Python 3.10+**
- **Docker** (with Docker Compose v2)
- **Git**
- **SSH client** (for remote deployment mode only)

> The wizard checks for these automatically and shows install links if anything is missing.

## Quick Start

### Interactive mode (recommended)

```bash
uv run erpnext-setup-wizard.py
```

The wizard will guide you through deployment mode selection, configuration, and setup.

### Skip the language picker

```bash
uv run erpnext-setup-wizard.py --lang en
```

Available codes: `en`, `tr`, `de`, `es`, `fr`, `it`

### Using pip instead of uv

```bash
pip install rich questionary pyyaml
python erpnext-setup-wizard.py
```

## Deployment Modes

### Local Development

For testing on your machine. Uses HTTP on a custom port with automatic hosts file update.

```bash
uv run erpnext-setup-wizard.py
# Select "Local Development" when prompted
# Access at http://mysite.localhost:8080
```

### Production Server

For real servers with a domain. Uses Traefik reverse proxy with automatic Let's Encrypt SSL.

```bash
uv run erpnext-setup-wizard.py
# Select "Production Server" when prompted
# Access at https://erp.example.com
```

### Remote Server (SSH)

Deploy to a remote server from your local machine. The wizard runs locally and executes all commands on the remote server via SSH.

```bash
uv run erpnext-setup-wizard.py
# Select "Remote Server (SSH)" when prompted
# Provide SSH host, user, and optional key path
```

**Requirements on the remote server:** Docker, Docker Compose, and Git.

## Unattended Mode

Skip all interactive prompts for automated deployments.

### Using a YAML config file

```bash
uv run erpnext-setup-wizard.py --config deploy.yml
```

Example `deploy.yml`:

```yaml
mode: production
site_name: erp.example.com
erpnext_version: v16.7.3
db_type: mariadb
db_password: secure_password
admin_password: admin_password
domain: erp.example.com
letsencrypt_email: admin@example.com
extra_apps:
  - hrms
  - payments

smtp:
  host: smtp.gmail.com
  port: 587
  user: noreply@example.com
  password: app_password
  use_tls: true

backup:
  s3_endpoint: https://s3.amazonaws.com
  s3_bucket: erp-backups
  s3_access_key: AKIA...
  s3_secret_key: secret

ssh:                          # only for remote mode
  host: 192.168.1.100
  user: deploy
  port: 22
  key_path: ~/.ssh/id_rsa
```

### Using CLI flags

```bash
uv run erpnext-setup-wizard.py \
  --mode production \
  --site-name erp.example.com \
  --version v16.7.3 \
  --db-type mariadb \
  --db-password secure_password \
  --admin-password admin_password \
  --domain erp.example.com \
  --letsencrypt-email admin@example.com \
  --apps hrms,payments
```

## What the Wizard Does

### Step 1 — Prerequisite Check

Verifies Docker, Docker Compose, and Git are installed. For remote mode, also tests SSH connectivity and checks tools on the remote server. Clones [frappe_docker](https://github.com/frappe/frappe_docker) if not already present.

### Step 2 — Configuration

Prompts for deployment mode, then mode-specific settings:

| Setting | Local | Production | Remote |
|---------|-------|------------|--------|
| Site name | mysite.localhost | erp.example.com | erp.example.com |
| ERPNext version | Autocomplete from GitHub | Same | Same |
| Database type | MariaDB / PostgreSQL | Same | Same |
| HTTP port | 1024-65535 | — | — |
| Domain + SSL email | — | Required | Required |
| SSH details | — | — | Required |
| Passwords | Required | Required | Required |
| Optional apps | Checkbox | Checkbox | Checkbox |
| SMTP config | — | Optional | Optional |
| S3 backup | — | Optional | Optional |

### Step 3 — Environment File

Generates the `.env` file with your configuration. Production/remote modes include Traefik SSL variables (`SITES_RULE`, `LETSENCRYPT_EMAIL`).

### Step 4 — Docker Compose

Starts the container stack with the correct overlay files:
- **Database:** `compose.mariadb.yaml` or `compose.postgres.yaml`
- **Proxy:** `compose.noproxy.yaml` (local) or `compose.https.yaml` (production/remote)

### Step 5 — Site Creation

- Creates the ERPNext site with `bench new-site`
- Enables the scheduler
- Installs selected optional and community apps
- Configures SMTP email settings (if provided)
- Configures S3 backup (if provided)
- Updates hosts file (local mode only)
- Shows the completion banner with URL and credentials

## After Setup

Open the URL shown in the completion banner:

| Mode | URL | Protocol |
|------|-----|----------|
| Local | `http://mysite.localhost:8080` | HTTP |
| Production | `https://erp.example.com` | HTTPS (auto-SSL) |
| Remote | `https://erp.example.com` | HTTPS (auto-SSL) |

Log in with **User:** `Administrator` and the admin password you entered.

## Project Structure

```
erpnext-setup-wizard.py      Entry point (PEP 723 inline metadata)
wizard/
├── theme.py                 Console, colors, questionary style
├── ui.py                    Banner, step headers, progress bar
├── utils.py                 Shell runner, tool checker
├── prompts.py               Input fields (text, password, version, select, apps)
├── ssh.py                   Executor pattern (LocalExecutor, SSHExecutor)
├── config_loader.py         CLI flags + YAML config parser
├── versions.py              GitHub API version fetcher
├── apps.py                  Optional Frappe apps registry + branch detection
├── community_apps.py        Community app discovery from awesome-frappe
├── i18n/
│   ├── __init__.py          Translation engine (dot-notation keys)
│   ├── en.json              English
│   ├── tr.json              Turkish
│   ├── de.json              German
│   ├── es.json              Spanish
│   ├── fr.json              French
│   └── it.json              Italian
└── steps/
    ├── __init__.py           Step count + exports
    ├── prerequisites.py      Step 1: Docker/Git/SSH checks
    ├── configure.py          Step 2: 25-field Config dataclass + prompts
    ├── env_file.py           Step 3: Mode-aware .env generation
    ├── docker.py             Step 4: Dynamic compose command
    └── site.py               Step 5: Site creation, SMTP, backup, banner
```

## Adding a Language

1. Copy `wizard/i18n/en.json` to `wizard/i18n/{code}.json`
2. Translate all values (keep keys and `{placeholder}` variables unchanged)
3. Set `"lang_name"` to the language's native name (e.g., `"Deutsch"`)
4. The wizard picks it up automatically — no code changes needed

## Troubleshooting

**"Docker not found"** — Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and make sure it's running.

**Port already in use** — Choose a different HTTP port (e.g., `8081`).

**Hosts file permission error** — The wizard shows the exact line to add manually. On Linux/macOS, edit `/etc/hosts` with sudo. On Windows, run your terminal as Administrator.

**SSH connection failed** — Verify you can connect manually: `ssh user@host`. Check that the remote server has Docker and Docker Compose installed.

**SSL certificate not issued** — Make sure your domain's DNS A record points to your server's IP address. Let's Encrypt needs to reach port 80 for HTTP challenge validation.

**Optional app installation fails** — The wizard skips failed apps and continues with the rest. You can install them later manually:
```bash
docker compose exec backend bench get-app --branch version-16 <app_name>
docker compose exec backend bench --site <site_name> install-app <app_name>
```

## License

MIT
