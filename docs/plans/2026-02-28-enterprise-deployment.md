# Enterprise Deployment Evolution — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Evolve the wizard from localhost-only to support 3 deployment modes: local, production (HTTPS/Traefik), and remote SSH — plus unattended mode via CLI flags and YAML config.

**Architecture:** Monolithic refactor of existing step-based wizard. Add `deploy_mode` field to Config, branch logic per mode in each step. New `wizard/ssh.py` (executor pattern) and `wizard/config_loader.py` (CLI/YAML parsing). frappe_docker's `compose.https.yaml` for production SSL.

**Tech Stack:** Python 3.10+, Rich, questionary, PyYAML (new dep), subprocess SSH/SCP

---

## Context for Implementers

### Project Structure
```
wizard/
├── theme.py            — Console, colors, Q_STYLE
├── ui.py               — banner(), step_header(), ok/fail/step/info()
├── utils.py            — run(), check_tool(), version_branch(), clear_screen()
├── prompts.py          — ask_field(), ask_version_field(), ask_password_field(), ask_apps_field(), confirm_action()
├── apps.py             — OPTIONAL_APPS, detect_best_branch()
├── community_apps.py   — fetch_community_apps()
├── versions.py         — fetch_erpnext_versions()
├── i18n/__init__.py    — t(), init(), select_language()
├── i18n/{en,tr,de,es,fr,it}.json
└── steps/
    ├── __init__.py         — TOTAL_STEPS, re-exports
    ├── prerequisites.py    — Step 1
    ├── configure.py        — Step 2 (Config dataclass + prompts)
    ├── env_file.py         — Step 3
    ├── docker.py           — Step 4 (COMPOSE_CMD constant)
    └── site.py             — Step 5
```

### Key Patterns
- i18n: `t("steps.configure.key")` — dot notation, kwargs for interpolation
- Validators: return `True` on success, error string via `t(...)` on failure
- Shell commands: `shlex.quote()` for all user values
- All steps import `TOTAL_STEPS` from `wizard.steps`
- `run(cmd, capture=False)` returns `int` or `tuple[int, str, str]`
- Entry point: `erpnext-setup-wizard.py` with `argparse`

### frappe_docker Compose Overrides (available in cloned repo)
- `compose.yaml` — base services (backend, frontend, websocket, configurator, queues)
- `overrides/compose.mariadb.yaml` — MariaDB service
- `overrides/compose.postgres.yaml` — PostgreSQL service
- `overrides/compose.redis.yaml` — Redis service
- `overrides/compose.noproxy.yaml` — Direct HTTP (frontend ports 8080)
- `overrides/compose.https.yaml` — Traefik proxy + Let's Encrypt SSL (ports 80/443)
  - Requires: `LETSENCRYPT_EMAIL`, `SITES_RULE` (e.g. `Host(\`erp.example.com\`)`)

---

### Task 1: Add PyYAML Dependency

**Files:**
- Modify: `erpnext-setup-wizard.py:4` (dependencies line)

**Step 1: Add PyYAML to inline script metadata**

The project uses PEP 723 inline script metadata. Add `pyyaml>=6.0` to the dependencies list:

```python
# /// script
# requires-python = ">=3.10"
# dependencies = ["rich>=13.9.0", "questionary>=2.1.0", "pyyaml>=6.0"]
# ///
```

**Step 2: Verify the dependency resolves**

Run: `cd C:/Users/clawd/Desktop/erpnext-setup-wizard && uv run python -c "import yaml; print(yaml.__version__)"`
Expected: prints a version number (e.g. `6.0.1`)

**Step 3: Commit**

```bash
git add erpnext-setup-wizard.py
git commit -m "deps: add PyYAML for config file support"
```

---

### Task 2: Create Executor Pattern (`wizard/ssh.py`)

**Files:**
- Create: `wizard/ssh.py`

This is the core abstraction that lets all step functions work identically for local and remote deployment.

**Step 1: Create `wizard/ssh.py` with LocalExecutor and SSHExecutor**

```python
"""Execution backends: local subprocess and remote SSH."""

import shlex
import subprocess


class LocalExecutor:
    """Execute commands on the local machine via subprocess."""

    def run(self, cmd: str, capture: bool = False) -> int | tuple[int, str, str]:
        if capture:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result.returncode, result.stdout, result.stderr
        else:
            result = subprocess.run(cmd, shell=True)
            return result.returncode

    def upload(self, local_path: str, remote_path: str):
        """Local-to-local copy (used when executor interface requires upload)."""
        import shutil
        shutil.copy2(local_path, remote_path)


class SSHExecutor:
    """Execute commands on a remote server via SSH."""

    def __init__(self, host: str, user: str, port: int = 22,
                 key_path: str = ""):
        self.host = host
        self.user = user
        self.port = port
        self.key_path = key_path

    def _ssh_base(self) -> list[str]:
        """Build base SSH command parts."""
        parts = ["ssh", "-o", "StrictHostKeyChecking=accept-new",
                 "-p", str(self.port)]
        if self.key_path:
            parts.extend(["-i", self.key_path])
        parts.append(f"{self.user}@{self.host}")
        return parts

    def _scp_base(self) -> list[str]:
        """Build base SCP command parts."""
        parts = ["scp", "-o", "StrictHostKeyChecking=accept-new",
                 "-P", str(self.port)]
        if self.key_path:
            parts.extend(["-i", self.key_path])
        return parts

    def run(self, cmd: str, capture: bool = False) -> int | tuple[int, str, str]:
        """Run a command on the remote host via SSH."""
        full_cmd = self._ssh_base() + [cmd]
        if capture:
            result = subprocess.run(full_cmd, capture_output=True, text=True)
            return result.returncode, result.stdout, result.stderr
        else:
            result = subprocess.run(full_cmd)
            return result.returncode

    def upload(self, local_path: str, remote_path: str):
        """Upload a file to the remote host via SCP."""
        dest = f"{self.user}@{self.host}:{remote_path}"
        full_cmd = self._scp_base() + [local_path, dest]
        result = subprocess.run(full_cmd)
        if result.returncode != 0:
            raise RuntimeError(f"SCP upload failed: {local_path} -> {dest}")

    def test_connection(self) -> bool:
        """Test SSH connectivity. Returns True on success."""
        code, _, _ = self.run("echo ok", capture=True)
        return code == 0


def create_executor(cfg) -> "LocalExecutor | SSHExecutor":
    """Factory: create the right executor based on deploy_mode."""
    if cfg.deploy_mode == "remote":
        return SSHExecutor(
            host=cfg.ssh_host,
            user=cfg.ssh_user,
            port=cfg.ssh_port,
            key_path=cfg.ssh_key_path,
        )
    return LocalExecutor()
```

**Step 2: Verify import works**

Run: `cd C:/Users/clawd/Desktop/erpnext-setup-wizard && uv run python -c "from wizard.ssh import LocalExecutor, SSHExecutor; print('ok')"`
Expected: `ok`

**Step 3: Commit**

```bash
git add wizard/ssh.py
git commit -m "feat: add executor pattern for local and SSH command execution"
```

---

### Task 3: Expand Config Dataclass & Deploy Mode Prompt

**Files:**
- Modify: `wizard/steps/configure.py`
- Modify: `wizard/prompts.py`

**Step 1: Add `ask_select_field` to prompts.py**

We need a new prompt type for single-selection lists (deploy mode, db type). Add after `ask_apps_field`:

```python
def ask_select_field(
    number: int,
    icon: str,
    label: str,
    choices: list[tuple[str, str]],
    hint: str = "",
) -> str:
    """Single-select field using questionary.select.

    Args:
        choices: list of (value, display_label) tuples
    Returns:
        selected value
    """
    _field_header(number, icon, label)
    if hint:
        console.print(f"      [{MUTED}]{hint}[/]")

    q_choices = [
        questionary.Choice(title=display, value=value)
        for value, display in choices
    ]

    selected = questionary.select(
        message="",
        choices=q_choices,
        qmark="      ▸",
        style=Q_STYLE,
    ).ask()

    if selected is None:
        _cancelled()

    # Find display name for confirmation
    display = next(d for v, d in choices if v == selected)
    console.print(f"      [bold {OK}]✔[/] [green]{display}[/green]")
    console.print()
    return selected
```

**Step 2: Expand Config dataclass in configure.py**

Replace the existing Config with all new fields. Every new field has a default so existing code stays compatible:

```python
@dataclass
class Config:
    """Holds all user-supplied configuration values."""
    # Core
    deploy_mode: str = "local"          # "local" | "production" | "remote"
    site_name: str = ""
    erpnext_version: str = ""
    db_type: str = "mariadb"            # "mariadb" | "postgres"
    http_port: str = "8080"             # local mode only
    db_password: str = ""
    admin_password: str = ""
    extra_apps: list[str] = field(default_factory=list)
    community_apps: list[CommunityApp] = field(default_factory=list)

    # Production + Remote
    domain: str = ""                    # e.g. "erp.example.com"
    letsencrypt_email: str = ""         # e.g. "admin@example.com"

    # Remote SSH
    ssh_host: str = ""
    ssh_user: str = "root"
    ssh_port: int = 22
    ssh_key_path: str = ""             # "" = use default/agent

    # Optional: SMTP
    smtp_host: str = ""                # "" = skip
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True

    # Optional: Backup (S3-compatible)
    backup_enabled: bool = False
    backup_s3_endpoint: str = ""
    backup_s3_bucket: str = ""
    backup_s3_access_key: str = ""
    backup_s3_secret_key: str = ""
```

**Step 3: Add deploy mode + SSH + DB type + domain + SMTP + backup prompts to `run_configure()`**

The new prompt flow (within the existing `while True` loop):

```python
from ..prompts import ask_field, ask_password_field, ask_version_field, ask_apps_field, ask_select_field, confirm_action

def run_configure() -> Config:
    step_header(2, TOTAL_STEPS, t("steps.configure.title"))

    while True:
        console.print(
            Panel(
                f"[dim]{t('steps.configure.intro')}[/dim]",
                box=box.ROUNDED,
                border_style=MUTED,
                padding=(0, 2),
            )
        )
        console.print()

        # ❶ Deploy mode
        deploy_mode = ask_select_field(
            number=1,
            icon="🚀",
            label=t("steps.configure.deploy_mode"),
            hint=t("steps.configure.deploy_mode_hint"),
            choices=[
                ("local", t("steps.configure.deploy_local")),
                ("production", t("steps.configure.deploy_production")),
                ("remote", t("steps.configure.deploy_remote")),
            ],
        )

        # ❷ SSH details (remote only)
        ssh_host = ssh_user = ssh_key_path = ""
        ssh_port = 22
        if deploy_mode == "remote":
            console.print(Rule(style="dim"))
            console.print()

            ssh_host = ask_field(
                number=2, icon="🖥️",
                label=t("steps.configure.ssh_host"),
                hint=t("steps.configure.ssh_host_hint"),
                examples="192.168.1.100 · erp.example.com",
            )
            ssh_user = ask_field(
                number=3, icon="👤",
                label=t("steps.configure.ssh_user"),
                hint=t("steps.configure.ssh_user_hint"),
                default="root",
            )
            ssh_port_str = ask_field(
                number=4, icon="🔌",
                label=t("steps.configure.ssh_port"),
                default="22",
                validate=_validate_ssh_port,
            )
            ssh_port = int(ssh_port_str)
            ssh_key_path = ask_field(
                number=5, icon="🔑",
                label=t("steps.configure.ssh_key"),
                hint=t("steps.configure.ssh_key_hint"),
                default="",
            )

        # ❸ Site name — field number shifts based on mode
        n = 6 if deploy_mode == "remote" else 2
        site_default = "mysite.localhost" if deploy_mode == "local" else "erp.example.com"
        site_name = ask_field(
            number=n, icon="🌐",
            label=t("steps.configure.site_name"),
            hint=t("steps.configure.site_name_hint"),
            examples="spaceflow.localhost · erp.localhost" if deploy_mode == "local" else "erp.example.com · crm.mycompany.com",
            default=site_default,
            validate=_validate_site_name,
        )
        n += 1

        # ❹ ERPNext version
        step(t("steps.configure.fetching_versions"))
        versions = fetch_erpnext_versions()
        if versions:
            ok(t("steps.configure.versions_loaded", count=len(versions)))
            default_version = versions[0]
        else:
            fail(t("steps.configure.versions_failed"))
            versions = None
            default_version = "v16.7.3"
        console.print()

        erpnext_version = ask_version_field(
            number=n, icon="📦",
            label=t("steps.configure.erpnext_version"),
            hint=t("steps.configure.erpnext_version_hint"),
            choices=versions,
            default=default_version,
        )
        n += 1

        # ❺ Database type
        db_type = ask_select_field(
            number=n, icon="🗄️",
            label=t("steps.configure.db_type"),
            hint=t("steps.configure.db_type_hint"),
            choices=[
                ("mariadb", "MariaDB"),
                ("postgres", "PostgreSQL"),
            ],
        )
        n += 1

        # ❻ HTTP port (local only) or Domain + SSL (production/remote)
        domain = ""
        letsencrypt_email = ""
        http_port = "8080"
        if deploy_mode == "local":
            http_port = ask_field(
                number=n, icon="🔌",
                label=t("steps.configure.http_port"),
                hint=t("steps.configure.http_port_hint"),
                default="8080",
                validate=_validate_port,
            )
        else:
            domain = ask_field(
                number=n, icon="🌍",
                label=t("steps.configure.domain"),
                hint=t("steps.configure.domain_hint"),
                examples="erp.example.com · crm.mycompany.com",
                default=site_name,
                validate=_validate_domain,
            )
            n += 1
            letsencrypt_email = ask_field(
                number=n, icon="📧",
                label=t("steps.configure.letsencrypt_email"),
                hint=t("steps.configure.letsencrypt_email_hint"),
                examples="admin@example.com",
                validate=_validate_email,
            )
        n += 1

        console.print(Rule(style="dim"))
        console.print()

        # ❼ Passwords
        db_password = ask_password_field(number=n, icon="🔒", label=t("steps.configure.db_password"))
        n += 1
        admin_password = ask_password_field(number=n, icon="🔑", label=t("steps.configure.admin_password"))
        n += 1

        # ❽ Optional apps + community apps (same as current)
        console.print(Rule(style="dim"))
        console.print()
        app_choices = [
            (app.repo_name, f"{app.display_name} — {t(app.i18n_key)}")
            for app in OPTIONAL_APPS
        ]
        extra_apps = ask_apps_field(number=n, icon="📦", label=t("steps.configure.extra_apps"), choices=app_choices)
        n += 1

        console.print()
        step(t("steps.configure.fetching_community_apps"))
        community_app_list = fetch_community_apps(erpnext_version)
        community_apps: list[CommunityApp] = []
        if community_app_list:
            ok(t("steps.configure.community_apps_loaded", count=len(community_app_list)))
            console.print()
            community_choices = [
                (app.repo_name, f"{app.display_name} ({app.repo_name})")
                for app in community_app_list
            ]
            selected_community = ask_apps_field(
                number=n, icon="🌐",
                label=t("steps.configure.community_apps"),
                choices=community_choices,
                hint_key="steps.configure.community_apps_hint",
                none_key="steps.configure.community_apps_none",
                selected_key="steps.configure.community_apps_selected",
            )
            selected_set = set(selected_community)
            community_apps = [app for app in community_app_list if app.repo_name in selected_set]
        else:
            fail(t("steps.configure.community_apps_failed"))
        n += 1

        # ❾ SMTP (optional, production/remote only)
        smtp_host = smtp_user = smtp_password = ""
        smtp_port = 587
        smtp_use_tls = True
        if deploy_mode != "local":
            console.print(Rule(style="dim"))
            console.print()
            if confirm_action(t("steps.configure.smtp_configure")):
                smtp_host = ask_field(number=n, icon="📧", label=t("steps.configure.smtp_host"), examples="smtp.gmail.com · mail.example.com")
                n += 1
                smtp_port_str = ask_field(number=n, icon="🔌", label=t("steps.configure.smtp_port"), default="587")
                smtp_port = int(smtp_port_str)
                n += 1
                smtp_user = ask_field(number=n, icon="👤", label=t("steps.configure.smtp_user"))
                n += 1
                smtp_password = ask_password_field(number=n, icon="🔑", label=t("steps.configure.smtp_password"))
                n += 1
                smtp_use_tls = confirm_action(t("steps.configure.smtp_use_tls"))
            else:
                n += 1

        # ❿ Backup (optional, production/remote only)
        backup_enabled = False
        backup_s3_endpoint = backup_s3_bucket = backup_s3_access_key = backup_s3_secret_key = ""
        if deploy_mode != "local":
            console.print()
            if confirm_action(t("steps.configure.backup_configure")):
                backup_enabled = True
                backup_s3_endpoint = ask_field(number=n, icon="☁️", label=t("steps.configure.backup_s3_endpoint"), examples="https://s3.amazonaws.com · https://minio.example.com")
                n += 1
                backup_s3_bucket = ask_field(number=n, icon="🪣", label=t("steps.configure.backup_s3_bucket"), examples="erp-backups")
                n += 1
                backup_s3_access_key = ask_field(number=n, icon="🔑", label=t("steps.configure.backup_s3_access_key"))
                n += 1
                backup_s3_secret_key = ask_password_field(number=n, icon="🔐", label=t("steps.configure.backup_s3_secret_key"))
                n += 1

        # Summary table + confirmation (expanded)
        # ... (same pattern as current, with new rows for deploy_mode, db_type, domain, etc.)

        if confirm_action(t("steps.configure.confirm")):
            return Config(
                deploy_mode=deploy_mode,
                site_name=site_name,
                erpnext_version=erpnext_version,
                db_type=db_type,
                http_port=http_port,
                db_password=db_password,
                admin_password=admin_password,
                extra_apps=extra_apps,
                community_apps=community_apps,
                domain=domain,
                letsencrypt_email=letsencrypt_email,
                ssh_host=ssh_host,
                ssh_user=ssh_user,
                ssh_port=ssh_port,
                ssh_key_path=ssh_key_path,
                smtp_host=smtp_host,
                smtp_port=smtp_port,
                smtp_user=smtp_user,
                smtp_password=smtp_password,
                smtp_use_tls=smtp_use_tls,
                backup_enabled=backup_enabled,
                backup_s3_endpoint=backup_s3_endpoint,
                backup_s3_bucket=backup_s3_bucket,
                backup_s3_access_key=backup_s3_access_key,
                backup_s3_secret_key=backup_s3_secret_key,
            )

        if not confirm_action(t("steps.configure.confirm_declined")):
            console.print(Panel(f"[yellow]{t('steps.configure.cancelled')}[/yellow]", border_style=WARN))
            sys.exit(0)
        console.print()
```

**New validators to add in configure.py:**

```python
def _validate_ssh_port(val: str) -> bool | str:
    if val.isdigit() and val == str(int(val)) and 1 <= int(val) <= 65535:
        return True
    return t("steps.configure.ssh_port_invalid")

def _validate_domain(val: str) -> bool | str:
    if re.fullmatch(r"[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)+", val):
        return True
    return t("steps.configure.domain_invalid")

def _validate_email(val: str) -> bool | str:
    if re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", val):
        return True
    return t("steps.configure.email_invalid")
```

**Updated summary table**: Add rows for deploy mode, db type, domain (if production/remote), SSH host (if remote), SMTP host (if configured), backup endpoint (if configured). Show `http_port` only for local mode.

**Step 4: Verify the module imports cleanly**

Run: `cd C:/Users/clawd/Desktop/erpnext-setup-wizard && uv run python -c "from wizard.steps.configure import Config; c = Config(); print(c.deploy_mode, c.db_type)"`
Expected: `local mariadb`

**Step 5: Commit**

```bash
git add wizard/prompts.py wizard/steps/configure.py
git commit -m "feat: add deploy mode, DB type, SSH, domain, SMTP, backup prompts"
```

---

### Task 4: Dynamic COMPOSE_CMD in docker.py

**Files:**
- Modify: `wizard/steps/docker.py`

**Step 1: Replace hardcoded COMPOSE_CMD with `build_compose_cmd(cfg)`**

The current `docker.py` has a module-level `COMPOSE_CMD` constant used by both `docker.py` and `site.py`. Replace it with a function and pass the command string through Config or as an argument.

```python
"""Step 4: Start Docker Compose containers."""

import shlex
import sys

from ..theme import console
from ..ui import step_header, step, ok, fail, info, animated_wait
from ..i18n import t
from .configure import Config
from . import TOTAL_STEPS


def build_compose_cmd(cfg: Config) -> str:
    """Build the docker compose command with correct override files."""
    files = ["compose.yaml"]

    # Database
    if cfg.db_type == "postgres":
        files.append("overrides/compose.postgres.yaml")
    else:
        files.append("overrides/compose.mariadb.yaml")

    # Redis (always)
    files.append("overrides/compose.redis.yaml")

    # Proxy
    if cfg.deploy_mode == "local":
        files.append("overrides/compose.noproxy.yaml")
    else:
        files.append("overrides/compose.https.yaml")

    return "docker compose " + " ".join(f"-f {f}" for f in files)


def run_docker(cfg: Config, executor):
    """Bring up Docker Compose stack."""
    step_header(4, TOTAL_STEPS, t("steps.docker.title"))

    compose_cmd = build_compose_cmd(cfg)

    step(t("steps.docker.cleaning"))
    code = executor.run(f"{compose_cmd} down")
    if code != 0:
        fail(t("steps.docker.down_failed"))
        sys.exit(1)
    ok(t("steps.docker.cleaned"))

    console.print()
    step(t("steps.docker.starting"))
    info(t("steps.docker.first_time_hint"))
    code = executor.run(f"{compose_cmd} up -d")
    if code != 0:
        fail(t("steps.docker.start_failed"))
        sys.exit(1)
    ok(t("steps.docker.running"))

    console.print()
    wait_time = 35 if cfg.deploy_mode == "remote" else 25
    animated_wait(wait_time, t("steps.docker.waiting_db"))
```

**Important**: `site.py` currently imports `COMPOSE_CMD` from `docker.py`. After this change, `site.py` must call `build_compose_cmd(cfg)` instead. This will be handled in Task 7.

**Step 2: Update `wizard/steps/__init__.py`** — `run_docker` now takes `(cfg, executor)` instead of no args.

**Step 3: Commit**

```bash
git add wizard/steps/docker.py
git commit -m "feat: dynamic compose command based on deploy mode and DB type"
```

---

### Task 5: Mode-Aware Env File Generation

**Files:**
- Modify: `wizard/steps/env_file.py`

**Step 1: Rewrite `run_env_file` to generate mode-specific .env**

```python
"""Step 3: Write the .env file."""

import os

from ..ui import step_header, step, ok, info
from ..utils import version_branch
from .configure import Config
from ..i18n import t
from . import TOTAL_STEPS


def _env_quote(value: str) -> str:
    """Quote a value for safe .env file inclusion."""
    special = set("#$\"'`\\!&|;() \t\n")
    if any(c in special for c in value):
        escaped = value.replace("'", "'\\''")
        return f"'{escaped}'"
    return value


def _build_env_content(cfg: Config) -> str:
    """Build .env file content based on deploy mode."""
    frappe_ver = version_branch(cfg.erpnext_version)

    lines = [
        f"ERPNEXT_VERSION={cfg.erpnext_version}",
        f"FRAPPE_VERSION={frappe_ver}",
        f"DB_PASSWORD={_env_quote(cfg.db_password)}",
        f"FRAPPE_SITE_NAME_HEADER={cfg.site_name}",
    ]

    if cfg.deploy_mode == "local":
        lines.append(f"HTTP_PUBLISH_PORT={cfg.http_port}")
        lines.append("LETSENCRYPT_EMAIL=mail@example.com")
    else:
        # Production / Remote: Traefik + Let's Encrypt
        lines.append(f"LETSENCRYPT_EMAIL={cfg.letsencrypt_email}")
        # SITES_RULE for compose.https.yaml frontend routing
        lines.append(f"SITES_RULE=Host(`{cfg.domain}`)")

    return "\n".join(lines) + "\n"


def run_env_file(cfg: Config, executor):
    """Generate the .env file from configuration."""
    step_header(3, TOTAL_STEPS, t("steps.env_file.title"))

    step(t("steps.env_file.writing"))
    env_content = _build_env_content(cfg)

    if cfg.deploy_mode == "remote":
        # Write locally first, then upload
        tmp_path = ".env.remote.tmp"
        with open(tmp_path, "w") as f:
            f.write(env_content)
        executor.upload(tmp_path, "~/frappe_docker/.env")
        os.unlink(tmp_path)
        info(t("steps.env_file.uploaded"))
    else:
        # Local / production: write directly
        tmp_path = ".env.tmp"
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w") as f:
                f.write(env_content)
            os.replace(tmp_path, ".env")
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    ok(t("steps.env_file.done"))
```

**Step 2: Commit**

```bash
git add wizard/steps/env_file.py
git commit -m "feat: mode-aware .env generation with Traefik/SSL support"
```

---

### Task 6: Mode-Aware Prerequisites

**Files:**
- Modify: `wizard/steps/prerequisites.py`

**Step 1: Rewrite `run_prerequisites` to accept Config and handle remote checks**

```python
"""Step 1: Check Docker, Docker Compose, Git, and frappe_docker repo."""

import os
import sys

from ..ui import step_header, step, ok, fail, info
from ..utils import check_tool, run
from ..ssh import SSHExecutor
from ..i18n import t
from . import TOTAL_STEPS
from .configure import Config


def _check_remote_tool(executor: SSHExecutor, name: str, cmd: str) -> bool:
    """Check a tool exists on the remote host."""
    step(t("steps.prerequisites.checking_remote", name=name))
    code, out, _ = executor.run(cmd, capture=True)
    if code != 0:
        fail(t("steps.prerequisites.remote_not_found", name=name))
        return False
    version = out.strip()
    ok(t("steps.prerequisites.remote_found", name=name, version=version))
    return True


def run_prerequisites(cfg: Config, executor):
    """Run prerequisite checks. Exits on failure."""
    step_header(1, TOTAL_STEPS, t("steps.prerequisites.title"))

    if cfg.deploy_mode == "remote":
        # Check local SSH tools
        ssh_ver = check_tool("SSH", "ssh -V 2>&1")
        if not ssh_ver:
            info(t("steps.prerequisites.install_ssh"))
            sys.exit(1)

        # Test SSH connection
        step(t("steps.prerequisites.testing_ssh"))
        if not executor.test_connection():
            fail(t("steps.prerequisites.ssh_failed"))
            sys.exit(1)
        ok(t("steps.prerequisites.ssh_ok"))

        from ..theme import console
        console.print()

        # Check remote tools
        if not _check_remote_tool(executor, "Docker", "docker --version"):
            sys.exit(1)
        if not _check_remote_tool(executor, "Docker Compose", "docker compose version"):
            sys.exit(1)
        if not _check_remote_tool(executor, "Git", "git --version"):
            sys.exit(1)

        # Clone frappe_docker on remote if needed
        console.print()
        step(t("steps.prerequisites.checking_remote_folder"))
        code, _, _ = executor.run("test -f ~/frappe_docker/compose.yaml", capture=True)
        if code != 0:
            step(t("steps.prerequisites.cloning_repo_remote"))
            code = executor.run(
                "git clone https://github.com/frappe/frappe_docker ~/frappe_docker"
            )
            if code != 0:
                fail(t("steps.prerequisites.clone_failed"))
                sys.exit(1)
            ok(t("steps.prerequisites.repo_downloaded"))
        else:
            ok(t("steps.prerequisites.remote_folder_exists"))

    else:
        # Local / Production: existing logic
        docker_ver = check_tool("Docker", "docker --version")
        if not docker_ver:
            info(t("steps.prerequisites.install_docker"))
            sys.exit(1)

        compose_ver = check_tool("Docker Compose", "docker compose version")
        if not compose_ver:
            sys.exit(1)

        from ..theme import console
        console.print()
        step(t("steps.prerequisites.checking_folder"))

        if not os.path.exists("compose.yaml"):
            info(t("steps.prerequisites.compose_not_found"))

            git_ver = check_tool("Git", "git --version")
            if not git_ver:
                info(t("steps.prerequisites.install_git"))
                sys.exit(1)

            if not os.path.exists("frappe_docker"):
                step(t("steps.prerequisites.cloning_repo"))
                code = run("git clone https://github.com/frappe/frappe_docker")
                if code != 0:
                    fail(t("steps.prerequisites.clone_failed"))
                    sys.exit(1)
                ok(t("steps.prerequisites.repo_downloaded"))
            else:
                ok(t("steps.prerequisites.folder_exists"))

            os.chdir("frappe_docker")
            info(t("steps.prerequisites.working_dir", cwd=os.getcwd()))

        ok(t("steps.prerequisites.correct_dir"))
```

**Step 2: Commit**

```bash
git add wizard/steps/prerequisites.py
git commit -m "feat: mode-aware prerequisites with remote SSH checks"
```

---

### Task 7: Mode-Aware Site Creation & Completion

**Files:**
- Modify: `wizard/steps/site.py`

**Step 1: Update site.py to use executor pattern and build_compose_cmd**

Key changes:
1. Replace `from .docker import COMPOSE_CMD` with `from .docker import build_compose_cmd`
2. All `run(...)` calls become `executor.run(...)`
3. `bench new-site` gets `--db-type postgres` if `cfg.db_type == "postgres"`
4. Remote mode: prefix commands with `cd ~/frappe_docker &&`
5. SMTP config via `bench set-config` after site creation (if configured)
6. Backup config via `bench set-config` after site creation (if configured)
7. Hosts file: only in local mode
8. Completion banner: `https://domain` for production/remote, `http://site:port` for local
9. DNS reminder for production/remote

```python
"""Step 5: Create ERPNext site, configure hosts, show completion."""

import platform
import shlex
import sys

from rich.align import Align
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text
from rich.console import Group
from rich import box

from ..theme import console, ACCENT, OK, WARN, MUTED
from ..ui import step_header, step, ok, fail, info
from ..utils import version_branch
from ..apps import OPTIONAL_APPS, detect_best_branch
from .configure import Config
from ..i18n import t
from . import TOTAL_STEPS
from .docker import build_compose_cmd


def _create_site(cfg: Config, executor, compose_cmd: str):
    """Create the ERPNext site via bench, with retry on failure."""
    from ..prompts import confirm_action

    site_escaped = cfg.site_name.replace("[", "\\[")
    step(t("steps.site.creating", site_name=site_escaped))
    info(t("steps.site.creating_hint"))

    db_type_flag = ""
    if cfg.db_type == "postgres":
        db_type_flag = " --db-type postgres"

    while True:
        code = executor.run(
            f"{compose_cmd} exec -T backend bench new-site {shlex.quote(cfg.site_name)} "
            f"--install-app erpnext "
            f"--db-root-password {shlex.quote(cfg.db_password)} "
            f"--admin-password {shlex.quote(cfg.admin_password)}"
            f"{db_type_flag}"
        )
        if code == 0:
            break

        fail(t("steps.site.create_failed"))
        if not confirm_action(t("steps.site.create_retry")):
            sys.exit(1)
        console.print()
        step(t("steps.site.creating", site_name=site_escaped))

    ok(t("steps.site.created"))

    console.print()
    step(t("steps.site.enabling_scheduler"))
    code = executor.run(
        f"{compose_cmd} exec -T backend bench --site {shlex.quote(cfg.site_name)} enable-scheduler"
    )
    if code != 0:
        fail(t("steps.site.scheduler_failed"))
    else:
        ok(t("steps.site.scheduler_enabled"))


def _configure_smtp(cfg: Config, executor, compose_cmd: str):
    """Apply SMTP settings via bench set-config."""
    if not cfg.smtp_host:
        return

    console.print()
    step(t("steps.site.configuring_smtp"))
    site_q = shlex.quote(cfg.site_name)
    bench_cfg = f"{compose_cmd} exec -T backend bench --site {site_q} set-config"

    executor.run(f"{bench_cfg} mail_server {shlex.quote(cfg.smtp_host)}")
    executor.run(f"{bench_cfg} mail_port {cfg.smtp_port}")
    executor.run(f"{bench_cfg} mail_login {shlex.quote(cfg.smtp_user)}")
    executor.run(f"{bench_cfg} mail_password {shlex.quote(cfg.smtp_password)}")
    executor.run(f"{bench_cfg} use_tls {1 if cfg.smtp_use_tls else 0}")
    ok(t("steps.site.smtp_configured"))


def _configure_backup(cfg: Config, executor, compose_cmd: str):
    """Apply S3 backup settings via bench set-config."""
    if not cfg.backup_enabled:
        return

    console.print()
    step(t("steps.site.configuring_backup"))
    site_q = shlex.quote(cfg.site_name)
    bench_cfg = f"{compose_cmd} exec -T backend bench --site {site_q} set-config"

    executor.run(f"{bench_cfg} backup_bucket {shlex.quote(cfg.backup_s3_bucket)}")
    executor.run(f'{bench_cfg} backup_region ""')
    executor.run(f"{bench_cfg} backup_endpoint {shlex.quote(cfg.backup_s3_endpoint)}")
    executor.run(f"{bench_cfg} backup_access_key {shlex.quote(cfg.backup_s3_access_key)}")
    executor.run(f"{bench_cfg} backup_secret_key {shlex.quote(cfg.backup_s3_secret_key)}")
    ok(t("steps.site.backup_configured"))


# _install_app, _install_extra_apps, _install_community_apps
# Same as current but replace run() with executor.run() and
# COMPOSE_CMD with compose_cmd parameter.
# (Omitted for brevity — the pattern is identical, just pass executor and compose_cmd through.)


def _update_hosts(cfg: Config):
    """Add site to hosts file — LOCAL MODE ONLY."""
    if cfg.deploy_mode != "local":
        return

    # ... existing hosts file logic unchanged ...


def _show_done(cfg: Config):
    """Print the completion banner."""
    if cfg.deploy_mode == "local":
        url = f"http://{cfg.site_name}:{cfg.http_port}"
    else:
        url = f"https://{cfg.domain}"

    result_table = Table(box=box.SIMPLE_HEAVY, border_style=OK, padding=(0, 3), show_header=False)
    result_table.add_column(style="bold white")
    result_table.add_column(style=f"bold {ACCENT}")
    result_table.add_row("🌐  URL", url)
    result_table.add_row(f"👤  {t('steps.site.done_user')}", "Administrator")
    result_table.add_row(f"🔑  {t('steps.site.done_password')}", t("steps.site.done_password_hint"))

    if cfg.deploy_mode != "local":
        result_table.add_row(f"🔒  {t('steps.site.done_ssl')}", "Let's Encrypt (auto)")

    done_title = Text.assemble(
        ("\n🎉  ", ""),
        (t("steps.site.done_title"), "bold bright_green"),
        ("\n", ""),
    )
    done_footer_text = t("steps.site.done_open_browser", url=url)
    if cfg.deploy_mode != "local":
        done_footer_text += f"\n{t('steps.site.dns_reminder', domain=cfg.domain)}"

    done_footer = Text(f"\n{done_footer_text}\n", style=MUTED)

    console.print()
    console.print(
        Panel(
            Group(
                Align.center(done_title),
                Align.center(result_table),
                Align.center(done_footer),
            ),
            box=box.DOUBLE_EDGE,
            border_style=OK,
            padding=(1, 4),
        )
    )
    console.print()


def run_site(cfg: Config, executor):
    """Step 5: create site, install extra apps, update hosts, show done."""
    compose_cmd = build_compose_cmd(cfg)

    # Remote mode: all compose commands need cd prefix
    if cfg.deploy_mode == "remote":
        compose_cmd = f"cd ~/frappe_docker && {compose_cmd}"

    step_header(5, TOTAL_STEPS, t("steps.site.title"))
    _create_site(cfg, executor, compose_cmd)
    installed = _install_extra_apps(cfg, executor, compose_cmd) + _install_community_apps(cfg, executor, compose_cmd)
    if installed > 0:
        executor.run(f"{compose_cmd} restart frontend")
    _configure_smtp(cfg, executor, compose_cmd)
    _configure_backup(cfg, executor, compose_cmd)
    _update_hosts(cfg)
    _show_done(cfg)
```

**Step 2: Commit**

```bash
git add wizard/steps/site.py
git commit -m "feat: mode-aware site creation with SMTP, backup, and executor pattern"
```

---

### Task 8: Config Loader (CLI + YAML Unattended Mode)

**Files:**
- Create: `wizard/config_loader.py`
- Modify: `erpnext-setup-wizard.py`

**Step 1: Create `wizard/config_loader.py`**

```python
"""Load configuration from CLI arguments or YAML file for unattended mode."""

import argparse
import sys

import yaml

from .steps.configure import Config
from .community_apps import CommunityApp


def build_parser() -> argparse.ArgumentParser:
    """Build the full argument parser."""
    parser = argparse.ArgumentParser(
        description="ERPNext Setup Wizard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--lang", type=str, help="Language code (e.g., tr, en)")
    parser.add_argument("--config", type=str, help="Path to YAML config file for unattended mode")

    # Deploy mode
    parser.add_argument("--mode", choices=["local", "production", "remote"],
                        help="Deployment mode")
    parser.add_argument("--site-name", type=str)
    parser.add_argument("--version", type=str, help="ERPNext version (e.g., v16.7.3)")
    parser.add_argument("--db-type", choices=["mariadb", "postgres"], default=None)
    parser.add_argument("--http-port", type=str)
    parser.add_argument("--db-password", type=str)
    parser.add_argument("--admin-password", type=str)
    parser.add_argument("--domain", type=str)
    parser.add_argument("--letsencrypt-email", type=str)
    parser.add_argument("--apps", type=str, help="Comma-separated app names")

    # SSH
    parser.add_argument("--ssh-host", type=str)
    parser.add_argument("--ssh-user", type=str)
    parser.add_argument("--ssh-port", type=int)
    parser.add_argument("--ssh-key", type=str)

    # SMTP
    parser.add_argument("--smtp-host", type=str)
    parser.add_argument("--smtp-port", type=int)
    parser.add_argument("--smtp-user", type=str)
    parser.add_argument("--smtp-password", type=str)
    parser.add_argument("--smtp-no-tls", action="store_true")

    # Backup
    parser.add_argument("--backup-s3-endpoint", type=str)
    parser.add_argument("--backup-s3-bucket", type=str)
    parser.add_argument("--backup-s3-access-key", type=str)
    parser.add_argument("--backup-s3-secret-key", type=str)

    return parser


def _config_from_yaml(path: str) -> Config:
    """Parse a YAML config file into a Config object."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    smtp = data.get("smtp", {})
    backup = data.get("backup", {})
    ssh = data.get("ssh", {})

    return Config(
        deploy_mode=data.get("mode", "local"),
        site_name=data["site_name"],
        erpnext_version=data["erpnext_version"],
        db_type=data.get("db_type", "mariadb"),
        http_port=str(data.get("http_port", "8080")),
        db_password=data["db_password"],
        admin_password=data["admin_password"],
        extra_apps=data.get("extra_apps", []),
        community_apps=[],  # Community apps not supported in unattended mode
        domain=data.get("domain", ""),
        letsencrypt_email=data.get("letsencrypt_email", ""),
        ssh_host=ssh.get("host", ""),
        ssh_user=ssh.get("user", "root"),
        ssh_port=ssh.get("port", 22),
        ssh_key_path=ssh.get("key_path", ""),
        smtp_host=smtp.get("host", ""),
        smtp_port=smtp.get("port", 587),
        smtp_user=smtp.get("user", ""),
        smtp_password=smtp.get("password", ""),
        smtp_use_tls=smtp.get("use_tls", True),
        backup_enabled=bool(backup),
        backup_s3_endpoint=backup.get("s3_endpoint", ""),
        backup_s3_bucket=backup.get("s3_bucket", ""),
        backup_s3_access_key=backup.get("s3_access_key", ""),
        backup_s3_secret_key=backup.get("s3_secret_key", ""),
    )


def _config_from_args(args) -> Config | None:
    """Try to build Config from CLI args. Returns None if not enough args."""
    required = [args.mode, args.site_name, args.version,
                args.db_password, args.admin_password]
    if not all(required):
        return None

    return Config(
        deploy_mode=args.mode,
        site_name=args.site_name,
        erpnext_version=args.version,
        db_type=args.db_type or "mariadb",
        http_port=args.http_port or "8080",
        db_password=args.db_password,
        admin_password=args.admin_password,
        extra_apps=args.apps.split(",") if args.apps else [],
        community_apps=[],
        domain=args.domain or "",
        letsencrypt_email=args.letsencrypt_email or "",
        ssh_host=args.ssh_host or "",
        ssh_user=args.ssh_user or "root",
        ssh_port=args.ssh_port or 22,
        ssh_key_path=args.ssh_key or "",
        smtp_host=args.smtp_host or "",
        smtp_port=args.smtp_port or 587,
        smtp_user=args.smtp_user or "",
        smtp_password=args.smtp_password or "",
        smtp_use_tls=not args.smtp_no_tls,
        backup_enabled=bool(args.backup_s3_bucket),
        backup_s3_endpoint=args.backup_s3_endpoint or "",
        backup_s3_bucket=args.backup_s3_bucket or "",
        backup_s3_access_key=args.backup_s3_access_key or "",
        backup_s3_secret_key=args.backup_s3_secret_key or "",
    )


def load_config(args) -> Config | None:
    """Try to load config from YAML file or CLI args.

    Returns Config for unattended mode, or None to fall through to interactive.
    """
    if args.config:
        return _config_from_yaml(args.config)
    return _config_from_args(args)
```

**Step 2: Update entry point `erpnext-setup-wizard.py`**

```python
#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["rich>=13.9.0", "questionary>=2.1.0", "pyyaml>=6.0"]
# ///
"""
ERPNext Setup Wizard — frappe_docker
Premium terminal UI powered by Rich + questionary

Usage:
    uv run erpnext-setup-wizard.py
    uv run erpnext-setup-wizard.py --lang en
    uv run erpnext-setup-wizard.py --config deploy.yml
    uv run erpnext-setup-wizard.py --mode production --site-name erp.example.com ...
"""

import sys

from wizard.config_loader import build_parser, load_config
from wizard.i18n import init as i18n_init, select_language
from wizard.ui import banner
from wizard.utils import clear_screen
from wizard.ssh import create_executor
from wizard.steps import (
    run_prerequisites,
    run_configure,
    run_env_file,
    run_docker,
    run_site,
)


def main():
    parser = build_parser()
    args = parser.parse_args()

    lang = args.lang or "en"
    unattended_cfg = load_config(args)

    if not unattended_cfg and not args.lang:
        clear_screen()
        lang = select_language()

    i18n_init(lang)

    if not unattended_cfg:
        clear_screen()
        banner()

    # Step 2 — Configuration (interactive or unattended)
    if unattended_cfg:
        cfg = unattended_cfg
    else:
        cfg = run_configure()

    # Create executor based on deploy mode
    executor = create_executor(cfg)

    # Step 1 — Prerequisites
    run_prerequisites(cfg, executor)

    # Step 3 — .env File
    run_env_file(cfg, executor)

    # Step 4 — Docker Compose
    run_docker(cfg, executor)

    # Step 5 — Site Creation + Completion
    run_site(cfg, executor)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        from wizard.theme import console
        from wizard.i18n import t
        try:
            msg = t("common.interrupted")
        except Exception:
            msg = "Interrupted."
        console.print(f"\n  [yellow]{msg}[/yellow]")
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as e:
        from wizard.theme import console
        from wizard.i18n import t
        try:
            msg = t("common.unexpected_error", error=str(e))
        except Exception:
            msg = f"An unexpected error occurred: {e}"
        console.print(f"\n  [red]{msg}[/red]")
        sys.exit(1)
```

**Note:** In unattended mode, prerequisites run AFTER config is loaded (we already have Config). In interactive mode, config is collected at Step 2 as before, but prerequisites now also receive Config. The step ordering in unattended mode is: Config → Prerequisites → Env → Docker → Site.

**Step 3: Update `wizard/steps/__init__.py`**

The step function signatures have changed. Update the re-exports — no signature changes needed in `__init__.py` itself, but update `TOTAL_STEPS` and verify the imports still work.

**Step 4: Commit**

```bash
git add wizard/config_loader.py erpnext-setup-wizard.py wizard/steps/__init__.py
git commit -m "feat: add unattended mode with CLI flags and YAML config file"
```

---

### Task 9: i18n Keys for All 6 Languages

**Files:**
- Modify: `wizard/i18n/en.json`
- Modify: `wizard/i18n/tr.json`
- Modify: `wizard/i18n/de.json`
- Modify: `wizard/i18n/es.json`
- Modify: `wizard/i18n/fr.json`
- Modify: `wizard/i18n/it.json`

New keys needed (English values shown, translate for each language):

**In `steps.configure`:**
```json
"deploy_mode": "Deployment Mode",
"deploy_mode_hint": "Choose how to deploy ERPNext",
"deploy_local": "Local Development (localhost, HTTP)",
"deploy_production": "Production Server (domain, HTTPS)",
"deploy_remote": "Remote Server (SSH + HTTPS)",
"ssh_host": "Server Address",
"ssh_host_hint": "IP address or hostname of the remote server",
"ssh_user": "SSH Username",
"ssh_user_hint": "User with Docker permissions on the remote server",
"ssh_port": "SSH Port",
"ssh_port_invalid": "Enter a valid port number (1–65535)",
"ssh_key": "SSH Key Path (optional)",
"ssh_key_hint": "Leave empty to use SSH agent or default key",
"db_type": "Database Type",
"db_type_hint": "MariaDB is recommended for most deployments",
"domain": "Domain Name",
"domain_hint": "The public domain for your ERPNext instance",
"domain_invalid": "Enter a valid domain name (e.g., erp.example.com)",
"letsencrypt_email": "Let's Encrypt Email",
"letsencrypt_email_hint": "Used for SSL certificate notifications",
"email_invalid": "Enter a valid email address",
"smtp_configure": "Configure email sending (SMTP)?",
"smtp_host": "SMTP Server",
"smtp_port": "SMTP Port",
"smtp_user": "SMTP Username",
"smtp_password": "SMTP Password",
"smtp_use_tls": "Use TLS for SMTP?",
"backup_configure": "Configure S3 backup?",
"backup_s3_endpoint": "S3 Endpoint URL",
"backup_s3_bucket": "S3 Bucket Name",
"backup_s3_access_key": "S3 Access Key",
"backup_s3_secret_key": "S3 Secret Key"
```

**In `steps.prerequisites`:**
```json
"install_ssh": "SSH client not found. Install OpenSSH.",
"testing_ssh": "Testing SSH connection…",
"ssh_ok": "SSH connection successful.",
"ssh_failed": "SSH connection failed! Check your credentials.",
"checking_remote": "Checking {name} on remote server…",
"remote_not_found": "{name} not found on remote server!",
"remote_found": "{name} found on remote  →  {version}",
"checking_remote_folder": "Checking frappe_docker on remote server…",
"cloning_repo_remote": "Cloning repository on remote server…",
"remote_folder_exists": "frappe_docker already exists on remote server."
```

**In `steps.env_file`:**
```json
"uploaded": ".env file uploaded to remote server."
```

**In `steps.site`:**
```json
"configuring_smtp": "Configuring SMTP email settings…",
"smtp_configured": "SMTP email configured.",
"configuring_backup": "Configuring S3 backup settings…",
"backup_configured": "S3 backup configured.",
"done_ssl": "SSL",
"dns_reminder": "⚠ Make sure DNS for {domain} points to your server."
```

**Step 1: Add all keys to en.json**

Add the keys listed above into their respective sections.

**Step 2: Translate and add to tr.json, de.json, es.json, fr.json, it.json**

Use appropriate translations for each language. Follow existing translation quality and style in each file.

**Step 3: Commit**

```bash
git add wizard/i18n/*.json
git commit -m "i18n: add enterprise deployment keys for all 6 languages"
```

---

### Task 10: Update `wizard/steps/__init__.py` and Wire Everything Together

**Files:**
- Modify: `wizard/steps/__init__.py`

**Step 1: Update step function signatures and TOTAL_STEPS**

The step count remains 5 (the steps themselves haven't changed, just their internal behavior). Update the imports and verify all step functions now accept the new parameters:

```python
"""Wizard steps."""

TOTAL_STEPS = 5

from .prerequisites import run_prerequisites
from .configure import run_configure
from .env_file import run_env_file
from .docker import run_docker
from .site import run_site

__all__ = [
    "TOTAL_STEPS",
    "run_prerequisites",
    "run_configure",
    "run_env_file",
    "run_docker",
    "run_site",
]
```

No change needed here — the function signatures changed in their respective files, but the re-exports are the same.

**Step 2: Smoke test the full interactive flow**

Run: `cd C:/Users/clawd/Desktop/erpnext-setup-wizard && uv run python -c "from wizard.steps import run_prerequisites, run_configure, run_env_file, run_docker, run_site; print('all imports ok')"`
Expected: `all imports ok`

**Step 3: Smoke test the unattended config loading**

Run: `cd C:/Users/clawd/Desktop/erpnext-setup-wizard && uv run python -c "from wizard.config_loader import build_parser, load_config; p = build_parser(); a = p.parse_args([]); print(load_config(a))"`
Expected: `None` (no args = interactive mode)

**Step 4: Commit (if any wiring changes needed)**

```bash
git add wizard/steps/__init__.py
git commit -m "chore: wire up updated step signatures"
```

---

### Task 11: Integration Test — Full Flow Verification

**Step 1: Test import chain**

Run: `cd C:/Users/clawd/Desktop/erpnext-setup-wizard && uv run python -c "
from wizard.ssh import LocalExecutor, SSHExecutor, create_executor
from wizard.config_loader import build_parser, load_config
from wizard.steps.configure import Config
from wizard.steps.docker import build_compose_cmd

# Test LocalExecutor
e = LocalExecutor()
code, out, err = e.run('echo hello', capture=True)
assert code == 0 and 'hello' in out, f'LocalExecutor failed: {code} {out}'

# Test build_compose_cmd
cfg = Config(deploy_mode='local', db_type='mariadb')
cmd = build_compose_cmd(cfg)
assert 'compose.noproxy.yaml' in cmd and 'compose.mariadb.yaml' in cmd

cfg2 = Config(deploy_mode='production', db_type='postgres')
cmd2 = build_compose_cmd(cfg2)
assert 'compose.https.yaml' in cmd2 and 'compose.postgres.yaml' in cmd2

# Test config from CLI args
parser = build_parser()
args = parser.parse_args([
    '--mode', 'production',
    '--site-name', 'erp.test.com',
    '--version', 'v16.7.3',
    '--db-password', 'secret',
    '--admin-password', 'admin',
    '--domain', 'erp.test.com',
    '--letsencrypt-email', 'a@b.com',
])
c = load_config(args)
assert c.deploy_mode == 'production'
assert c.domain == 'erp.test.com'

print('All integration tests passed!')
"`

Expected: `All integration tests passed!`

**Step 2: Test YAML config loading**

Create a temporary test config:

```bash
cd C:/Users/clawd/Desktop/erpnext-setup-wizard && cat > /tmp/test-config.yml << 'EOF'
mode: production
site_name: erp.test.com
erpnext_version: v16.7.3
db_type: postgres
db_password: secret
admin_password: admin
domain: erp.test.com
letsencrypt_email: admin@test.com
extra_apps:
  - hrms
  - payments
smtp:
  host: smtp.gmail.com
  port: 587
  user: noreply@test.com
  password: apppass
  use_tls: true
backup:
  s3_endpoint: https://s3.amazonaws.com
  s3_bucket: erp-backups
  s3_access_key: AKIA
  s3_secret_key: secret
ssh:
  host: 192.168.1.100
  user: deploy
  port: 22
EOF
```

Run: `cd C:/Users/clawd/Desktop/erpnext-setup-wizard && uv run python -c "
from wizard.config_loader import build_parser, load_config
parser = build_parser()
args = parser.parse_args(['--config', '/tmp/test-config.yml'])
c = load_config(args)
assert c.deploy_mode == 'production'
assert c.db_type == 'postgres'
assert c.smtp_host == 'smtp.gmail.com'
assert c.backup_enabled == True
assert c.backup_s3_bucket == 'erp-backups'
assert c.ssh_host == '192.168.1.100'
assert c.extra_apps == ['hrms', 'payments']
print('YAML config test passed!')
"`

Expected: `YAML config test passed!`

**Step 3: Final commit if any fixes needed**

```bash
git commit -m "test: verify enterprise deployment integration"
```

---

## Task Dependency Graph

```
Task 1 (PyYAML dep)
Task 2 (ssh.py)
    ↓
Task 3 (Config + prompts) ← depends on Task 2 (imports ssh types)
    ↓
Task 4 (docker.py) ← depends on Task 3 (Config signature)
Task 5 (env_file.py) ← depends on Task 3
Task 6 (prerequisites.py) ← depends on Task 2 + Task 3
Task 7 (site.py) ← depends on Task 2 + Task 3 + Task 4
    ↓
Task 8 (config_loader + entry point) ← depends on Task 3
    ↓
Task 9 (i18n) ← independent, but best done after code is final
    ↓
Task 10 (wire + __init__.py) ← depends on all above
    ↓
Task 11 (integration test) ← depends on all above
```

**Recommended execution order:** 1 → 2 → 3 → 4, 5, 6 (parallel) → 7 → 8 → 9 → 10 → 11
