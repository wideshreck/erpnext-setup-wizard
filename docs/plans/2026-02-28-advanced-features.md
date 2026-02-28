# Advanced Features Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add all missing competitor features: custom private apps, post-install health check, automatic backup scheduling, upgrade command, multi-site support, custom Docker image build, exec command, Portainer integration, and container health monitoring.

**Architecture:** Extend the existing wizard with 9 new capabilities. Some are new Config fields + prompts (custom apps, backup cron, multi-site, Portainer). Others are new CLI subcommands (upgrade, exec). Health check and monitoring are post-install verification steps. Custom image build generates apps.json + runs `docker build`. The entry point gains `argparse` subcommands: `setup` (default/current flow), `upgrade`, `exec`, `status`.

**Tech Stack:** Python 3.10+, Rich, questionary, frappe_docker compose overlays (compose.backup-cron.yaml, compose.multi-bench.yaml, compose.multi-bench-ssl.yaml), ofelia cron scheduler, Docker healthcheck, Portainer CE.

---

### Task 1: Refactor CLI to Support Subcommands

**Files:**
- Modify: `wizard/config_loader.py`
- Modify: `erpnext-setup-wizard.py`

**Context:** Currently `build_parser()` uses flat `--flag` arguments. We need `argparse` subcommands so we can add `upgrade`, `exec`, and `status` alongside the default `setup` flow. The default (no subcommand) must remain backward-compatible — running `uv run erpnext-setup-wizard.py` without arguments should still launch the interactive wizard.

**Step 1: Refactor build_parser() to use subparsers**

In `wizard/config_loader.py`, refactor `build_parser()`:

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="ERPNext Setup Wizard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # Global flags (available to all subcommands)
    parser.add_argument("--lang", type=str, help="Language code (e.g., tr, en)")

    subparsers = parser.add_subparsers(dest="command")

    # --- setup (default) ---
    setup_p = subparsers.add_parser("setup", help="Set up a new ERPNext instance")
    setup_p.add_argument("--config", type=str, help="Path to YAML config file")
    setup_p.add_argument("--mode", choices=["local", "production", "remote"])
    setup_p.add_argument("--site-name", type=str)
    setup_p.add_argument("--version", type=str, help="ERPNext version (e.g., v16.7.3)")
    setup_p.add_argument("--db-type", choices=["mariadb", "postgres"], default=None)
    setup_p.add_argument("--http-port", type=str)
    setup_p.add_argument("--db-password", type=str)
    setup_p.add_argument("--admin-password", type=str)
    setup_p.add_argument("--domain", type=str)
    setup_p.add_argument("--letsencrypt-email", type=str)
    setup_p.add_argument("--apps", type=str, help="Comma-separated app names")
    # SSH
    setup_p.add_argument("--ssh-host", type=str)
    setup_p.add_argument("--ssh-user", type=str)
    setup_p.add_argument("--ssh-port", type=int)
    setup_p.add_argument("--ssh-key", type=str)
    # SMTP
    setup_p.add_argument("--smtp-host", type=str)
    setup_p.add_argument("--smtp-port", type=int)
    setup_p.add_argument("--smtp-user", type=str)
    setup_p.add_argument("--smtp-password", type=str)
    setup_p.add_argument("--smtp-no-tls", action="store_true")
    # Backup
    setup_p.add_argument("--backup-s3-endpoint", type=str)
    setup_p.add_argument("--backup-s3-bucket", type=str)
    setup_p.add_argument("--backup-s3-access-key", type=str)
    setup_p.add_argument("--backup-s3-secret-key", type=str)
    # NEW flags for new features
    setup_p.add_argument("--custom-apps", type=str,
                         help="Comma-separated custom app specs: url:branch,url2:branch2")
    setup_p.add_argument("--backup-cron", type=str, default="",
                         help="Backup cron schedule (e.g., '@every 6h')")
    setup_p.add_argument("--sites", type=str,
                         help="Comma-separated site names for multi-site")
    setup_p.add_argument("--enable-portainer", action="store_true")
    setup_p.add_argument("--build-image", action="store_true",
                         help="Build custom Docker image with selected apps baked in")
    setup_p.add_argument("--image-tag", type=str, default="custom-erpnext:latest")

    # --- upgrade ---
    upgrade_p = subparsers.add_parser("upgrade", help="Upgrade existing ERPNext to a new version")
    upgrade_p.add_argument("--version", type=str, help="Target ERPNext version")
    upgrade_p.add_argument("--project", type=str, default="frappe_docker",
                           help="Docker Compose project directory")
    upgrade_p.add_argument("--ssh-host", type=str)
    upgrade_p.add_argument("--ssh-user", type=str)
    upgrade_p.add_argument("--ssh-port", type=int)
    upgrade_p.add_argument("--ssh-key", type=str)

    # --- exec ---
    exec_p = subparsers.add_parser("exec", help="Open a shell in the backend container")
    exec_p.add_argument("--project", type=str, default="frappe_docker")
    exec_p.add_argument("--service", type=str, default="backend",
                        help="Container service name")
    exec_p.add_argument("--ssh-host", type=str)
    exec_p.add_argument("--ssh-user", type=str)
    exec_p.add_argument("--ssh-port", type=int)
    exec_p.add_argument("--ssh-key", type=str)

    # --- status ---
    status_p = subparsers.add_parser("status", help="Show container health status")
    status_p.add_argument("--project", type=str, default="frappe_docker")
    status_p.add_argument("--ssh-host", type=str)
    status_p.add_argument("--ssh-user", type=str)
    status_p.add_argument("--ssh-port", type=int)
    status_p.add_argument("--ssh-key", type=str)

    return parser
```

**Step 2: Update entry point for subcommands**

In `erpnext-setup-wizard.py`, update `main()` to dispatch based on `args.command`:

```python
def main():
    parser = build_parser()
    args = parser.parse_args()

    # Default to "setup" if no subcommand given
    command = args.command or "setup"

    lang = args.lang or "en"

    if command == "setup":
        _run_setup(args, lang)
    elif command == "upgrade":
        _run_upgrade(args, lang)
    elif command == "exec":
        _run_exec(args)
    elif command == "status":
        _run_status(args, lang)
```

Extract current setup flow into `_run_setup(args, lang)`. The `upgrade`, `exec`, `status` functions will be added in later tasks.

**Step 3: Update load_config() for backward compatibility**

Ensure `load_config(args)` handles the new `args` structure where flags like `--config` are now under the `setup` subparser. Use `getattr(args, 'config', None)` pattern.

**Step 4: Commit**

```
git commit -m "refactor: add CLI subcommands (setup, upgrade, exec, status)"
```

---

### Task 2: Custom Private App Support

**Files:**
- Modify: `wizard/steps/configure.py` — add custom app prompts + CustomApp dataclass field
- Modify: `wizard/steps/site.py` — install custom apps
- Modify: `wizard/config_loader.py` — parse --custom-apps flag and YAML custom_apps section
- Modify: `wizard/i18n/*.json` — 6 language files

**Context:** Users need to install private Frappe apps from custom Git URLs with optional branch and auth token. This extends beyond the hardcoded OPTIONAL_APPS and community app discovery.

**Step 1: Add custom_apps field to Config**

In `wizard/steps/configure.py`, add to Config dataclass:

```python
@dataclass
class Config:
    # ... existing 25 fields ...
    custom_apps: list[dict] = field(default_factory=list)
    # Each dict: {"url": "https://...", "branch": "main", "name": "app_name"}
```

**Step 2: Add interactive prompt for custom apps**

After the community apps prompt in `run_configure()`, add a loop that lets users enter custom Git URLs one by one:

```python
# Custom private apps
if confirm_action(t("steps.configure.custom_apps_prompt")):
    custom_apps = []
    while True:
        url = ask_field(n, "🔧", t("steps.configure.custom_app_url"),
                       hint=t("steps.configure.custom_app_url_hint"),
                       examples="https://github.com/myorg/myapp.git")
        if not url:
            break
        branch = ask_field(n, "🌿", t("steps.configure.custom_app_branch"),
                          default="main")
        # Extract repo_name from URL
        name = url.rstrip("/").rstrip(".git").split("/")[-1]
        custom_apps.append({"url": url, "branch": branch, "name": name})
        if not confirm_action(t("steps.configure.custom_app_add_another")):
            break
```

**Step 3: Install custom apps in site.py**

Add `_install_custom_apps()` function in `site.py` that iterates `cfg.custom_apps` and calls the existing `_install_app()` pipeline for each:

```python
def _install_custom_apps(cfg: Config, executor, compose_cmd: str) -> int:
    if not cfg.custom_apps:
        return 0
    console.print()
    failed = []
    for i, app in enumerate(cfg.custom_apps, 1):
        step(t("steps.site.installing_custom_apps", current=i, total=len(cfg.custom_apps)))
        info(t("steps.site.installing_custom_app", app=app["name"], url=app["url"]))
        if _install_app(app["name"], app["name"], app["url"], app["branch"],
                        cfg.site_name, "steps.site.custom_app_failed",
                        executor=executor, compose_cmd=compose_cmd):
            ok(t("steps.site.custom_app_installed", app=app["name"]))
        else:
            failed.append(app["name"])
    console.print()
    if failed:
        fail(t("steps.site.custom_apps_some_failed", failed=len(failed), total=len(cfg.custom_apps)))
    else:
        ok(t("steps.site.custom_apps_done", count=len(cfg.custom_apps)))
    return len(cfg.custom_apps) - len(failed)
```

Call it from `run_site()` after `_install_community_apps()`. Include its return value in the `installed` count for frontend restart.

**Step 4: Parse --custom-apps CLI flag and YAML**

In `config_loader.py`, parse `--custom-apps url1:branch1,url2:branch2` format and YAML `custom_apps` list:

```yaml
custom_apps:
  - url: https://github.com/myorg/myapp.git
    branch: main
  - url: https://gitlab.com/org/app2.git
    branch: develop
```

**Step 5: Add i18n keys to all 6 language files**

Keys: `custom_apps_prompt`, `custom_app_url`, `custom_app_url_hint`, `custom_app_branch`, `custom_app_add_another`, `installing_custom_apps`, `installing_custom_app`, `custom_app_installed`, `custom_app_failed`, `custom_apps_some_failed`, `custom_apps_done`

**Step 6: Commit**

```
git commit -m "feat: add custom private app support with Git URL and branch"
```

---

### Task 3: Post-Install Health Check

**Files:**
- Modify: `wizard/steps/site.py` — add health check after site creation
- Modify: `wizard/steps/docker.py` — replace blind sleep with health polling
- Modify: `wizard/i18n/*.json` — 6 language files

**Context:** After `docker compose up`, instead of a blind 25-35s sleep, poll container health. After site creation, verify all containers are running and healthy. This replaces the current `animated_wait()` with actual polling.

**Step 1: Add _wait_for_healthy() in docker.py**

Replace the blind `animated_wait()` with a polling loop:

```python
def _wait_for_healthy(cfg: Config, executor, compose_cmd: str, timeout: int = 120):
    """Poll container health until all services are running or timeout."""
    step(t("steps.docker.health_checking"))
    start = time.time()
    while time.time() - start < timeout:
        code, stdout, _ = executor.run(
            f"{compose_cmd} ps --format json", capture=True
        )
        if code == 0 and stdout.strip():
            lines = stdout.strip().split("\n")
            all_up = True
            for line in lines:
                try:
                    svc = json.loads(line)
                    state = svc.get("State", "")
                    if state not in ("running",):
                        all_up = False
                        break
                except (json.JSONDecodeError, KeyError):
                    all_up = False
                    break
            if all_up:
                ok(t("steps.docker.all_healthy"))
                return True
        time.sleep(5)
    fail(t("steps.docker.health_timeout"))
    return False
```

Keep the `animated_wait()` as a fallback for older Docker Compose versions that don't support `--format json`.

**Step 2: Add post-site health verification in site.py**

After the entire `run_site()` completes (before `_show_done()`), add a final health check:

```python
def _verify_health(cfg: Config, executor, compose_cmd: str):
    """Final health verification — check site is accessible."""
    console.print()
    step(t("steps.site.verifying_health"))
    code = executor.run(
        f"{compose_cmd} exec -T backend bench --site {shlex.quote(cfg.site_name)} doctor",
        capture=False
    )
    if code == 0:
        ok(t("steps.site.health_ok"))
    else:
        # Non-fatal — site may still be initializing
        info(t("steps.site.health_warning"))
```

**Step 3: Add i18n keys**

Keys: `health_checking`, `all_healthy`, `health_timeout`, `verifying_health`, `health_ok`, `health_warning`

**Step 4: Commit**

```
git commit -m "feat: add post-install health check with container polling"
```

---

### Task 4: Automatic Backup Schedule (Cron)

**Files:**
- Modify: `wizard/steps/configure.py` — add backup_cron prompt
- Modify: `wizard/steps/docker.py` — include compose.backup-cron.yaml overlay
- Modify: `wizard/steps/env_file.py` — add BACKUP_CRONSTRING to .env
- Modify: `wizard/config_loader.py` — parse --backup-cron and YAML
- Modify: `wizard/i18n/*.json` — 6 language files

**Context:** frappe_docker has `overrides/compose.backup-cron.yaml` which uses [ofelia](https://github.com/mcuadros/ofelia) to run `bench --site all backup` on a cron schedule. The schedule is controlled by `BACKUP_CRONSTRING` env var (default: `@every 6h`).

**Step 1: Add backup_cron field to Config**

```python
backup_cron: str = ""  # e.g., "@every 6h", empty = disabled
```

**Step 2: Add prompt in configure.py**

After the S3 backup config section (for production/remote only), ask:

```python
if cfg.backup_enabled or confirm_action(t("steps.configure.backup_cron_prompt")):
    cfg.backup_cron = ask_field(
        n, "⏰", t("steps.configure.backup_cron_label"),
        default="@every 6h",
        hint=t("steps.configure.backup_cron_hint"),
        examples="@every 6h, @every 12h, @daily"
    )
```

**Step 3: Include overlay in build_compose_cmd()**

In `wizard/steps/docker.py`:

```python
if cfg.backup_cron:
    files.append("overrides/compose.backup-cron.yaml")
```

**Step 4: Add BACKUP_CRONSTRING to .env**

In `wizard/steps/env_file.py`, `_build_env_content()`:

```python
if cfg.backup_cron:
    lines.append(f"BACKUP_CRONSTRING={_env_quote(cfg.backup_cron)}")
```

**Step 5: Parse in config_loader.py**

CLI: `--backup-cron "@every 6h"`
YAML: `backup_cron: "@every 6h"`

**Step 6: Add i18n keys, commit**

```
git commit -m "feat: add automatic backup scheduling with ofelia cron"
```

---

### Task 5: Upgrade Command

**Files:**
- Create: `wizard/commands/upgrade.py`
- Create: `wizard/commands/__init__.py`
- Modify: `erpnext-setup-wizard.py` — wire upgrade command
- Modify: `wizard/i18n/*.json` — 6 language files

**Context:** The `upgrade` subcommand updates an existing ERPNext installation to a new version. It reads the current `.env`, updates `ERPNEXT_VERSION` and `FRAPPE_VERSION`, pulls new images, and runs `bench migrate`.

**Step 1: Create wizard/commands/__init__.py**

Empty file — package marker.

**Step 2: Create wizard/commands/upgrade.py**

```python
"""Upgrade an existing ERPNext installation to a new version."""

import os
import re
import shlex
import sys

from ..theme import console
from ..ui import step, ok, fail, info, banner
from ..utils import version_branch
from ..versions import fetch_erpnext_versions
from ..prompts import ask_version_field, confirm_action
from ..ssh import LocalExecutor, SSHExecutor
from ..i18n import t


def _read_current_env(executor, project_dir: str) -> dict:
    """Read current .env values."""
    code, stdout, _ = executor.run(
        f"cat {project_dir}/.env", capture=True
    )
    if code != 0:
        return {}
    env = {}
    for line in stdout.strip().split("\n"):
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"')
    return env


def _build_compose_cmd(project_dir: str, env: dict, is_remote: bool) -> str:
    """Reconstruct compose command from existing overlay files."""
    files = ["compose.yaml"]
    # Detect DB type from existing overlays
    for overlay in ["overrides/compose.mariadb.yaml", "overrides/compose.postgres.yaml",
                    "overrides/compose.redis.yaml", "overrides/compose.noproxy.yaml",
                    "overrides/compose.https.yaml", "overrides/compose.backup-cron.yaml"]:
        # Check which files were used — we can detect from running containers
        files_str = " ".join(f"-f {f}" for f in files)
    # Simplest approach: use `docker compose config` to get running config
    cmd = f"docker compose " + " ".join(f"-f {f}" for f in files)
    if is_remote:
        cmd = f"cd {project_dir} && {cmd}"
    return cmd


def run_upgrade(args):
    """Execute the upgrade workflow."""
    # Determine executor
    if args.ssh_host:
        executor = SSHExecutor(
            host=args.ssh_host,
            user=args.ssh_user or "root",
            port=args.ssh_port or 22,
            key_path=args.ssh_key or "",
        )
        is_remote = True
    else:
        executor = LocalExecutor()
        is_remote = False

    project_dir = args.project
    if is_remote:
        project_dir = f"~/{args.project}"

    # Step 1: Read current version
    step(t("commands.upgrade.reading_env"))
    env = _read_current_env(executor, project_dir)
    current_version = env.get("ERPNEXT_VERSION", "unknown")
    ok(t("commands.upgrade.current_version", version=current_version))

    # Step 2: Select target version
    if args.version:
        target_version = args.version
    else:
        console.print()
        info(t("commands.upgrade.fetching_versions"))
        versions = fetch_erpnext_versions()
        target_version = ask_version_field(
            1, "🔄", t("commands.upgrade.select_version"),
            choices=versions, default=current_version,
        )

    if target_version == current_version:
        info(t("commands.upgrade.already_current"))
        return

    console.print()
    info(t("commands.upgrade.will_upgrade",
           current=current_version, target=target_version))

    if not confirm_action(t("commands.upgrade.confirm")):
        return

    # Step 3: Backup before upgrade
    step(t("commands.upgrade.backing_up"))
    compose_prefix = f"cd {project_dir} && " if is_remote else ""
    executor.run(
        f"{compose_prefix}docker compose exec -T backend "
        f"bench --site all backup"
    )
    ok(t("commands.upgrade.backup_done"))

    # Step 4: Update .env
    console.print()
    step(t("commands.upgrade.updating_env"))
    new_frappe = version_branch(target_version)
    executor.run(
        f"{compose_prefix}sed -i "
        f"'s/ERPNEXT_VERSION=.*/ERPNEXT_VERSION={shlex.quote(target_version)}/' .env"
    )
    executor.run(
        f"{compose_prefix}sed -i "
        f"'s/FRAPPE_VERSION=.*/FRAPPE_VERSION={shlex.quote(new_frappe)}/' .env"
    )
    ok(t("commands.upgrade.env_updated"))

    # Step 5: Pull new images and restart
    console.print()
    step(t("commands.upgrade.pulling_images"))
    executor.run(f"{compose_prefix}docker compose pull")
    ok(t("commands.upgrade.images_pulled"))

    console.print()
    step(t("commands.upgrade.restarting"))
    executor.run(f"{compose_prefix}docker compose up -d")
    ok(t("commands.upgrade.restarted"))

    # Step 6: Run migrate
    console.print()
    step(t("commands.upgrade.migrating"))
    code = executor.run(
        f"{compose_prefix}docker compose exec -T backend "
        f"bench --site all migrate"
    )
    if code == 0:
        ok(t("commands.upgrade.migrate_done"))
    else:
        fail(t("commands.upgrade.migrate_failed"))

    console.print()
    ok(t("commands.upgrade.complete", version=target_version))
```

**Step 3: Wire in entry point**

In `_run_upgrade(args, lang)`:
```python
from wizard.commands.upgrade import run_upgrade
i18n_init(lang)
banner()
run_upgrade(args)
```

**Step 4: Add i18n keys, commit**

```
git commit -m "feat: add upgrade command for updating ERPNext versions"
```

---

### Task 6: Multi-Site Support

**Files:**
- Modify: `wizard/steps/configure.py` — allow multiple site names
- Modify: `wizard/steps/env_file.py` — update FRAPPE_SITE_NAME_HEADER and SITES_RULE
- Modify: `wizard/steps/site.py` — create multiple sites in a loop
- Modify: `wizard/config_loader.py` — parse --sites flag and YAML
- Modify: `wizard/i18n/*.json` — 6 language files

**Context:** frappe_docker supports multiple sites on a single bench. `FRAPPE_SITE_NAME_HEADER` controls the default site. For multi-site with Traefik, `SITES_RULE` uses multiple Host matchers. Each site needs its own `bench new-site` + app installation.

**Step 1: Add extra_sites field to Config**

```python
extra_sites: list[dict] = field(default_factory=list)
# Each dict: {"name": "site2.example.com", "admin_password": "..."}
```

**Step 2: Add multi-site prompt in configure.py**

After the main site configuration (production/remote only):

```python
if cfg.deploy_mode != "local" and confirm_action(t("steps.configure.multi_site_prompt")):
    while True:
        site = ask_field(n, "🌐", t("steps.configure.extra_site_name"),
                        validate=_validate_site_name)
        if not site:
            break
        pwd = ask_password_field(n, "🔑",
                                t("steps.configure.extra_site_password"))
        cfg.extra_sites.append({"name": site, "admin_password": pwd})
        if not confirm_action(t("steps.configure.multi_site_add_another")):
            break
```

**Step 3: Update .env for multi-site**

In `_build_env_content()`:

```python
if cfg.extra_sites:
    all_domains = [cfg.domain] + [s["name"] for s in cfg.extra_sites]
    sites_rule = " || ".join(f"Host(`{d}`)" for d in all_domains)
    lines.append(f"SITES_RULE={sites_rule}")
```

**Step 4: Create extra sites in site.py**

After `_create_site()` for the main site, loop through `cfg.extra_sites`:

```python
for extra in cfg.extra_sites:
    _create_extra_site(extra, cfg, executor, compose_cmd)
```

Each extra site runs `bench new-site` with its own admin password and installs the same apps.

**Step 5: Parse --sites and YAML, add i18n keys, commit**

```yaml
extra_sites:
  - name: site2.example.com
    admin_password: password2
  - name: site3.example.com
    admin_password: password3
```

```
git commit -m "feat: add multi-site support for production/remote deployments"
```

---

### Task 7: Custom Docker Image Build

**Files:**
- Create: `wizard/commands/build.py`
- Modify: `wizard/config_loader.py` — add build subcommand args (already in Task 1)
- Modify: `wizard/steps/configure.py` — add build_image flag prompt
- Modify: `wizard/i18n/*.json` — 6 language files

**Context:** frappe_docker supports custom image builds via `APPS_JSON_BASE64` build arg. When `--build-image` is set, the wizard generates an `apps.json` with all selected apps (official + community + custom), base64-encodes it, and runs `docker build` with the custom Containerfile. This bakes apps into the image, eliminating runtime `bench get-app` calls.

**Step 1: Create wizard/commands/build.py**

```python
"""Build a custom Docker image with selected apps baked in."""

import base64
import json
import shlex

from ..theme import console
from ..ui import step, ok, fail, info
from ..i18n import t


def generate_apps_json(cfg) -> str:
    """Generate apps.json content from selected apps."""
    apps = [
        {"url": "https://github.com/frappe/erpnext", "branch": cfg.erpnext_version}
    ]
    for app_name in cfg.extra_apps:
        apps.append({
            "url": f"https://github.com/frappe/{app_name}",
            "branch": "version-" + cfg.erpnext_version.split(".")[0].lstrip("v"),
        })
    for app in getattr(cfg, "custom_apps", []):
        apps.append({"url": app["url"], "branch": app["branch"]})
    return json.dumps(apps)


def run_build_image(cfg, executor, compose_cmd: str):
    """Build custom Docker image with apps baked in."""
    step(t("commands.build.generating_apps_json"))
    apps_json = generate_apps_json(cfg)
    apps_b64 = base64.b64encode(apps_json.encode()).decode()
    ok(t("commands.build.apps_json_ready", count=len(json.loads(apps_json))))

    console.print()
    step(t("commands.build.building_image"))
    tag = getattr(cfg, "image_tag", "custom-erpnext:latest")
    frappe_branch = "version-" + cfg.erpnext_version.split(".")[0].lstrip("v")

    build_cmd = (
        f"docker build "
        f"--build-arg=APPS_JSON_BASE64={shlex.quote(apps_b64)} "
        f"--build-arg=FRAPPE_BRANCH={shlex.quote(frappe_branch)} "
        f"-t {shlex.quote(tag)} "
        f"-f images/custom/Containerfile ."
    )

    code = executor.run(build_cmd)
    if code == 0:
        ok(t("commands.build.image_built", tag=tag))
    else:
        fail(t("commands.build.build_failed"))
        return False

    return True
```

**Step 2: Integrate with setup flow**

When `cfg.build_image` is True, call `run_build_image()` before `run_docker()`. Then set `CUSTOM_IMAGE` and `CUSTOM_TAG` in the .env file:

```python
if cfg.build_image:
    lines.append(f"CUSTOM_IMAGE={cfg.image_tag.split(':')[0]}")
    lines.append(f"CUSTOM_TAG={cfg.image_tag.split(':')[1]}")
    lines.append("PULL_POLICY=never")
```

**Step 3: Add i18n keys, commit**

```
git commit -m "feat: add custom Docker image build with apps baked in"
```

---

### Task 8: Exec Command

**Files:**
- Create: `wizard/commands/exec.py`
- Modify: `erpnext-setup-wizard.py` — wire exec command

**Context:** Simple utility — opens an interactive shell in the backend container. Supports both local and remote (SSH) execution.

**Step 1: Create wizard/commands/exec.py**

```python
"""Open an interactive shell in a running ERPNext container."""

import os
import subprocess
import sys

from ..ssh import SSHExecutor


def run_exec(args):
    """Open interactive shell in the specified container service."""
    service = args.service or "backend"
    project = args.project

    if args.ssh_host:
        # Remote: SSH into server, then docker exec
        ssh_parts = ["ssh", "-t"]
        if args.ssh_key:
            ssh_parts.extend(["-i", args.ssh_key])
        if args.ssh_port:
            ssh_parts.extend(["-p", str(args.ssh_port)])
        user = args.ssh_user or "root"
        ssh_parts.append(f"{user}@{args.ssh_host}")
        ssh_parts.append(
            f"cd ~/{project} && docker compose exec {service} bash"
        )
        os.execvp("ssh", ssh_parts)
    else:
        # Local: direct docker compose exec
        os.chdir(project)
        os.execvp("docker", [
            "docker", "compose", "exec", service, "bash"
        ])
```

**Step 2: Wire in entry point, commit**

```
git commit -m "feat: add exec command for interactive container shell"
```

---

### Task 9: Portainer Integration (Optional)

**Files:**
- Modify: `wizard/steps/configure.py` — add portainer prompt
- Modify: `wizard/steps/docker.py` — add portainer compose service
- Modify: `wizard/steps/site.py` — show Portainer URL in done banner
- Modify: `wizard/i18n/*.json` — 6 language files

**Context:** Portainer CE provides a web UI for Docker container management. When enabled, the wizard adds a Portainer container alongside the ERPNext stack. Portainer runs on port 9443 (HTTPS) with its own admin setup.

**Step 1: Add enable_portainer field to Config**

```python
enable_portainer: bool = False
```

**Step 2: Add prompt in configure.py**

For production/remote modes:

```python
if cfg.deploy_mode != "local":
    cfg.enable_portainer = confirm_action(
        t("steps.configure.portainer_prompt")
    )
```

**Step 3: Generate Portainer compose overlay dynamically**

In `wizard/steps/docker.py`, when `cfg.enable_portainer` is True, write a `compose.portainer.yaml` overlay file:

```python
def _write_portainer_overlay(executor, cfg):
    content = """services:
  portainer:
    image: portainer/portainer-ce:latest
    restart: unless-stopped
    ports:
      - "9443:9443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - portainer_data:/data

volumes:
  portainer_data:
"""
    # Write to frappe_docker directory
    if cfg.deploy_mode == "remote":
        import tempfile, os
        tmp = tempfile.mktemp(suffix=".yaml")
        with open(tmp, "w") as f:
            f.write(content)
        executor.upload(tmp, "~/frappe_docker/compose.portainer.yaml")
        os.unlink(tmp)
    else:
        with open("compose.portainer.yaml", "w") as f:
            f.write(content)
```

Include `-f compose.portainer.yaml` in `build_compose_cmd()` when enabled.

**Step 4: Show Portainer URL in done banner**

In `_show_done()`:

```python
if cfg.enable_portainer:
    portainer_url = f"https://{cfg.domain}:9443" if cfg.deploy_mode != "local" else "https://localhost:9443"
    result_table.add_row(f"🖥️  {t('steps.site.done_portainer')}", portainer_url)
```

**Step 5: Add i18n keys, commit**

```
git commit -m "feat: add optional Portainer web UI for container management"
```

---

### Task 10: Container Health Monitoring (Autoheal)

**Files:**
- Modify: `wizard/steps/configure.py` — add autoheal prompt
- Modify: `wizard/steps/docker.py` — add autoheal compose service
- Modify: `wizard/i18n/*.json` — 6 language files

**Context:** The [willfarrell/autoheal](https://github.com/willfarrell/docker-autoheal) container monitors other containers and automatically restarts any with an unhealthy status. frappe_docker's `compose.mariadb-shared.yaml` already includes healthchecks for MariaDB.

**Step 1: Add enable_autoheal field to Config**

```python
enable_autoheal: bool = False
```

**Step 2: Add prompt in configure.py**

For production/remote modes:

```python
if cfg.deploy_mode != "local":
    cfg.enable_autoheal = confirm_action(
        t("steps.configure.autoheal_prompt")
    )
```

**Step 3: Generate autoheal compose overlay**

Similar to Portainer, write a `compose.autoheal.yaml`:

```yaml
services:
  autoheal:
    image: willfarrell/autoheal:latest
    restart: always
    environment:
      AUTOHEAL_CONTAINER_LABEL: all
      AUTOHEAL_INTERVAL: 60
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
```

**Step 4: Add i18n keys, commit**

```
git commit -m "feat: add optional autoheal for automatic container recovery"
```

---

### Task 11: Status Command

**Files:**
- Create: `wizard/commands/status.py`
- Modify: `erpnext-setup-wizard.py` — wire status command
- Modify: `wizard/i18n/*.json` — 6 language files

**Context:** The `status` command shows the health of all containers, current ERPNext version, site info, and resource usage. It presents a Rich-formatted table.

**Step 1: Create wizard/commands/status.py**

```python
"""Show the status of a running ERPNext installation."""

import json

from rich.table import Table
from rich import box

from ..theme import console, OK, WARN, ERR, ACCENT
from ..ui import step, ok, fail
from ..ssh import LocalExecutor, SSHExecutor
from ..i18n import t


def run_status(args):
    """Display container health, versions, and resource usage."""
    if args.ssh_host:
        executor = SSHExecutor(
            host=args.ssh_host,
            user=args.ssh_user or "root",
            port=args.ssh_port or 22,
            key_path=args.ssh_key or "",
        )
        project_dir = f"~/{args.project}"
        cd_prefix = f"cd {project_dir} && "
    else:
        executor = LocalExecutor()
        cd_prefix = ""

    # Get container status
    code, stdout, _ = executor.run(
        f"{cd_prefix}docker compose ps --format json", capture=True
    )

    if code != 0:
        fail(t("commands.status.not_running"))
        return

    table = Table(
        title=t("commands.status.title"),
        box=box.ROUNDED,
        border_style=ACCENT,
    )
    table.add_column(t("commands.status.service"), style="bold")
    table.add_column(t("commands.status.state"))
    table.add_column(t("commands.status.health"))
    table.add_column(t("commands.status.ports"))

    for line in stdout.strip().split("\n"):
        try:
            svc = json.loads(line)
            name = svc.get("Service", svc.get("Name", "?"))
            state = svc.get("State", "?")
            health = svc.get("Health", "-")
            ports = svc.get("Publishers", "")
            if isinstance(ports, list):
                ports = ", ".join(
                    f"{p.get('PublishedPort', '')}→{p.get('TargetPort', '')}"
                    for p in ports if p.get("PublishedPort")
                )

            state_style = OK if state == "running" else ERR
            health_style = OK if health == "healthy" else (WARN if health == "-" else ERR)

            table.add_row(
                name,
                f"[{state_style}]{state}[/]",
                f"[{health_style}]{health}[/]",
                str(ports),
            )
        except (json.JSONDecodeError, KeyError):
            continue

    console.print(table)

    # Show current version from .env
    code, stdout, _ = executor.run(
        f"{cd_prefix}cat .env", capture=True
    )
    if code == 0:
        for line in stdout.split("\n"):
            if line.startswith("ERPNEXT_VERSION="):
                version = line.split("=", 1)[1].strip().strip('"')
                console.print(f"\n  ERPNext: [bold {ACCENT}]{version}[/]")
```

**Step 2: Wire in entry point, add i18n keys, commit**

```
git commit -m "feat: add status command showing container health and versions"
```

---

### Task 12: Update Config, README, and i18n for All Features

**Files:**
- Modify: `README.md` — document all new features and commands
- Modify: `wizard/steps/__init__.py` — no TOTAL_STEPS change needed (still 5 setup steps)
- Verify all i18n keys across 6 languages

**Step 1: Update README with new sections**

Add documentation for:
- Custom private apps (interactive + YAML + CLI)
- Backup cron scheduling
- `upgrade` subcommand
- `exec` subcommand
- `status` subcommand
- Multi-site setup
- Custom Docker image build
- Portainer integration
- Autoheal monitoring
- Updated YAML config example with all new fields
- Updated CLI flags reference

**Step 2: Final i18n consistency check**

Run the 6-language key comparison script. Ensure all new keys exist in all files.

**Step 3: Final import verification**

Run Python import check to verify all new modules wire correctly.

**Step 4: Commit**

```
git commit -m "docs: update README and i18n for all advanced features"
```

---

## Execution Summary

| Task | Feature | Files Changed |
|------|---------|--------------|
| 1 | CLI subcommands refactor | config_loader.py, entry point |
| 2 | Custom private app support | configure.py, site.py, config_loader.py, i18n |
| 3 | Post-install health check | docker.py, site.py, i18n |
| 4 | Automatic backup cron | configure.py, docker.py, env_file.py, config_loader.py, i18n |
| 5 | Upgrade command | NEW commands/upgrade.py, entry point, i18n |
| 6 | Multi-site support | configure.py, env_file.py, site.py, config_loader.py, i18n |
| 7 | Custom Docker image build | NEW commands/build.py, configure.py, env_file.py, i18n |
| 8 | Exec command | NEW commands/exec.py, entry point |
| 9 | Portainer integration | configure.py, docker.py, site.py, i18n |
| 10 | Autoheal monitoring | configure.py, docker.py, i18n |
| 11 | Status command | NEW commands/status.py, entry point, i18n |
| 12 | README + final verification | README.md, i18n verification |
