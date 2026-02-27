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

- **Guided setup** — prompts for site name, ERPNext version, port, passwords, and optional apps
- **Version selector** — fetches all stable ERPNext releases (v14+) from GitHub with autocomplete search
- **Optional Frappe apps** — install HRMS, Payments, Healthcare, Education, Lending, Webshop, Print Designer, or Wiki with a checkbox
- **Multi-language** — English, Turkish, German, Spanish, French, Italian
- **Input validation** — site name format, port range (1024-65535), password confirmation
- **Fail-soft app installation** — if one optional app fails, the rest continue
- **Automatic hosts file update** — adds `127.0.0.1 yoursite.localhost` (with permission fallback instructions)

## Prerequisites

- **Python 3.10+**
- **Docker Desktop** (with Docker Compose v2)
- **Git**

> The wizard checks for these automatically and shows install links if anything is missing.

## Quick Start

### Option 1: Using [uv](https://docs.astral.sh/uv/) (recommended)

No install needed. uv handles dependencies automatically:

```bash
uv run erpnext-setup-wizard.py
```

### Option 2: Using pip

```bash
pip install rich questionary
python erpnext-setup-wizard.py
```

### Skip the language picker

```bash
uv run erpnext-setup-wizard.py --lang en
```

Available codes: `en`, `tr`, `de`, `es`, `fr`, `it`

## What the Wizard Does

The wizard walks you through 5 steps:

### Step 1 — Prerequisite Check

Verifies Docker, Docker Compose, and Git are installed. Clones [frappe_docker](https://github.com/frappe/frappe_docker) if not already present.

### Step 2 — Configuration

Prompts for:

| Setting | Default | Validation |
|---------|---------|------------|
| Site name | `mysite.localhost` | Must contain a dot, no spaces |
| ERPNext version | Latest stable | Autocomplete from GitHub releases |
| HTTP port | `8080` | 1024–65535, no leading zeros |
| Database password | — | Min 6 chars, confirmation required |
| Admin password | — | Min 6 chars, confirmation required |
| Extra apps | None | Checkbox selection |

**Available optional apps:**

| App | Description |
|-----|-------------|
| HRMS | HR and Payroll Management |
| Payments | Payment Gateway Integrations |
| Healthcare | Health Management System |
| Education | Education Management System |
| Lending | Loan Management |
| Webshop | E-Commerce Platform |
| Print Designer | Print Format Designer |
| Wiki | Knowledge Base System |

A summary table is shown for review before proceeding.

### Step 3 — Environment File

Generates the `.env` file with your configuration. The `FRAPPE_VERSION` is derived automatically from the ERPNext version (e.g., `v16.7.3` &rarr; `version-16`).

### Step 4 — Docker Compose

Starts the container stack (MariaDB, Redis, backend, frontend). First run pulls images and may take 5-10 minutes.

### Step 5 — Site Creation

- Creates the ERPNext site with `bench new-site`
- Enables the scheduler
- Installs selected optional apps (clone, pip install, register, build assets)
- Updates the hosts file
- Shows the completion banner with your URL and credentials

## After Setup

Open the URL shown in the completion banner (e.g., `http://mysite.localhost:8080`), log in with:

- **User:** `Administrator`
- **Password:** the admin password you entered

## Project Structure

```
erpnext-setup-wizard.py     Entry point
wizard/
├── theme.py                Console, colors, questionary style
├── ui.py                   Banner, step headers, progress bar
├── utils.py                Shell runner, tool checker
├── prompts.py              Input fields (text, password, version, apps)
├── versions.py             GitHub API version fetcher
├── apps.py                 Optional Frappe apps registry
├── i18n/
│   ├── __init__.py         Translation engine (dot-notation keys)
│   ├── en.json             English
│   ├── tr.json             Turkish
│   ├── de.json             German
│   ├── es.json             Spanish
│   ├── fr.json             French
│   └── it.json             Italian
└── steps/
    ├── __init__.py          Step count + exports
    ├── prerequisites.py     Step 1: Docker/Git checks
    ├── configure.py         Step 2: User configuration
    ├── env_file.py          Step 3: .env generation
    ├── docker.py            Step 4: Container orchestration
    └── site.py              Step 5: Site creation + apps
```

## Adding a Language

1. Copy `wizard/i18n/en.json` to `wizard/i18n/{code}.json`
2. Translate all values (keep keys and `{placeholder}` variables unchanged)
3. Set `"lang_name"` to the language's native name (e.g., `"Deutsch"`)
4. The wizard picks it up automatically — no code changes needed

## Troubleshooting

**"Docker not found"** — Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) and make sure it's running.

**Port already in use** — Choose a different HTTP port (e.g., `8081`).

**Hosts file permission error** — The wizard shows the exact line to add manually. On Linux/macOS, edit `/etc/hosts` with sudo. On Windows, run your terminal as Administrator or edit `C:\Windows\System32\drivers\etc\hosts`.

**Optional app installation fails** — The wizard skips failed apps and continues with the rest. You can install them later manually:
```bash
docker compose exec backend bench get-app --branch version-16 <app_name>
docker compose exec backend bench --site <site_name> install-app <app_name>
```

## License

MIT
