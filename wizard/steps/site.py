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

    db_type_flag = " --db-type postgres" if cfg.db_type == "postgres" else ""

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
    code = executor.run(f"{compose_cmd} exec -T backend bench --site {shlex.quote(cfg.site_name)} enable-scheduler")
    if code != 0:
        fail(t("steps.site.scheduler_failed"))
    else:
        ok(t("steps.site.scheduler_enabled"))


def _create_extra_site(extra: dict, cfg: Config, executor, compose_cmd: str):
    """Create an additional site with the same apps."""
    site_escaped = extra["name"].replace("[", "\\[")
    step(t("steps.site.creating_extra_site", site_name=site_escaped))

    db_type_flag = " --db-type postgres" if cfg.db_type == "postgres" else ""
    site_q = shlex.quote(extra["name"])

    code = executor.run(
        f"{compose_cmd} exec -T backend bench new-site {site_q} "
        f"--install-app erpnext "
        f"--db-root-password {shlex.quote(cfg.db_password)} "
        f"--admin-password {shlex.quote(extra['admin_password'])}"
        f"{db_type_flag}"
    )
    if code == 0:
        ok(t("steps.site.extra_site_created", site_name=extra["name"]))
        # Enable scheduler
        executor.run(f"{compose_cmd} exec -T backend bench --site {site_q} enable-scheduler")
    else:
        fail(t("steps.site.extra_site_failed", site_name=extra["name"]))


def _install_app(repo_name: str, display_name: str, source: str,
                  branch: str, site_name: str, fail_key: str,
                  executor=None, compose_cmd: str = "") -> bool:
    """Run the 6-step install pipeline for a single Frappe app.

    Docker production containers need explicit steps because
    ``bench get-app`` only clones the repo without pip-installing or
    registering the app in ``sites/apps.txt``.

    Returns True on success, False on failure.
    """
    app_q = shlex.quote(repo_name)
    site_q = shlex.quote(site_name)
    branch_q = shlex.quote(branch)
    source_q = shlex.quote(source)

    # Step 1: Clone app repo
    code = executor.run(
        f"{compose_cmd} exec -T backend bench get-app "
        f"--branch {branch_q} {source_q}"
    )
    if code != 0:
        fail(t(fail_key, app=display_name))
        return False

    # Step 2: pip install (bench get-app skips this in production containers)
    code = executor.run(f"{compose_cmd} exec -T backend pip install -e apps/{app_q}")
    if code != 0:
        fail(t(fail_key, app=display_name))
        return False

    # Step 3: Register in apps.txt if missing
    executor.run(
        f"{compose_cmd} exec -T backend bash -c "
        f"'grep -qxF \"$1\" sites/apps.txt || echo \"$1\" >> sites/apps.txt' _ {app_q}"
    )

    # Step 4: Install on site
    code = executor.run(
        f"{compose_cmd} exec -T backend bench --site {site_q} "
        f"install-app {app_q}"
    )
    if code != 0:
        fail(t(fail_key, app=display_name))
        return False

    # Step 5: Build assets (CSS, JS, images)
    build_code = executor.run(f"{compose_cmd} exec -T backend bench build --app {app_q}")
    if build_code != 0:
        fail(t("steps.site.app_build_failed", app=display_name))
        return False

    # Step 6: Copy assets to frontend container.
    # bench build creates a symlink sites/assets/{app} -> apps/{app}/.../public
    # but the frontend container doesn't have the apps/ volume, so the
    # symlink is dangling.  Replace it with the actual files.
    executor.run(
        f"{compose_cmd} exec -T backend bash -c "
        f"'if [ -L \"sites/assets/$1\" ]; then "
        f"target=$(readlink -f \"sites/assets/$1\") && "
        f"rm \"sites/assets/$1\" && "
        f"cp -r \"$target\" \"sites/assets/$1\"; fi' _ {app_q}"
    )

    return True


def _install_extra_apps(cfg: Config, executor, compose_cmd: str) -> int:
    """Download and install selected extra apps. Fail-soft per app.

    Returns the number of successfully installed apps.
    """
    if not cfg.extra_apps:
        return 0

    default_branch = version_branch(cfg.erpnext_version)
    app_branch_map = {app.repo_name: app.branch for app in OPTIONAL_APPS}
    console.print()
    failed = []

    for i, app_name in enumerate(cfg.extra_apps, 1):
        step(t("steps.site.installing_apps", current=i, total=len(cfg.extra_apps)))
        info(t("steps.site.installing_app", app=app_name))

        # Smart branch: explicit override > detected > default
        branch = app_branch_map.get(app_name)
        if not branch:
            detected = detect_best_branch(
                f"https://github.com/frappe/{app_name}.git",
                cfg.erpnext_version,
            )
            branch = detected or default_branch

        # source=app_name: bench get-app resolves to github.com/frappe/{name}
        if _install_app(app_name, app_name, app_name, branch,
                        cfg.site_name, "steps.site.app_failed",
                        executor=executor, compose_cmd=compose_cmd):
            ok(t("steps.site.app_installed", app=app_name))
        else:
            failed.append(app_name)

    console.print()
    if failed:
        fail(t("steps.site.apps_some_failed", failed=len(failed), total=len(cfg.extra_apps)))
    else:
        ok(t("steps.site.apps_done", count=len(cfg.extra_apps)))

    return len(cfg.extra_apps) - len(failed)


def _install_community_apps(cfg: Config, executor, compose_cmd: str) -> int:
    """Install selected community apps. Fail-soft per app.

    Returns the number of successfully installed apps.
    """
    if not cfg.community_apps:
        return 0

    console.print()
    failed = []

    for i, app in enumerate(cfg.community_apps, 1):
        step(t("steps.site.installing_community_apps", current=i, total=len(cfg.community_apps)))
        info(t("steps.site.installing_community_app", app=app.display_name, url=app.repo_url))

        if _install_app(app.repo_name, app.display_name, app.repo_url,
                        app.branch, cfg.site_name, "steps.site.community_app_failed",
                        executor=executor, compose_cmd=compose_cmd):
            ok(t("steps.site.community_app_installed", app=app.display_name))
        else:
            failed.append(app.display_name)

    console.print()
    if failed:
        fail(t("steps.site.community_apps_some_failed", failed=len(failed), total=len(cfg.community_apps)))
    else:
        ok(t("steps.site.community_apps_done", count=len(cfg.community_apps)))

    return len(cfg.community_apps) - len(failed)


def _install_custom_apps(cfg: Config, executor, compose_cmd: str) -> int:
    """Install custom private apps from Git URLs.

    Returns the number of successfully installed apps.
    """
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


def _configure_smtp(cfg: Config, executor, compose_cmd: str):
    """Apply SMTP settings via bench set-config."""
    if not cfg.smtp_host:
        return
    console.print()
    step(t("steps.site.configuring_smtp"))
    site_q = shlex.quote(cfg.site_name)
    bench_cfg = f"{compose_cmd} exec -T backend bench --site {site_q} set-config"
    failed = False
    for code in [
        executor.run(f"{bench_cfg} mail_server {shlex.quote(cfg.smtp_host)}"),
        executor.run(f"{bench_cfg} mail_port {cfg.smtp_port}"),
        executor.run(f"{bench_cfg} mail_login {shlex.quote(cfg.smtp_user)}"),
        executor.run(f"{bench_cfg} mail_password {shlex.quote(cfg.smtp_password)}"),
        executor.run(f"{bench_cfg} use_tls {1 if cfg.smtp_use_tls else 0}"),
    ]:
        if code != 0:
            failed = True
    if failed:
        fail(t("steps.site.smtp_failed"))
    else:
        ok(t("steps.site.smtp_configured"))


def _configure_backup(cfg: Config, executor, compose_cmd: str):
    """Apply S3 backup settings via bench set-config."""
    if not cfg.backup_enabled:
        return
    console.print()
    step(t("steps.site.configuring_backup"))
    site_q = shlex.quote(cfg.site_name)
    bench_cfg = f"{compose_cmd} exec -T backend bench --site {site_q} set-config"
    failed = False
    for code in [
        executor.run(f"{bench_cfg} backup_bucket {shlex.quote(cfg.backup_s3_bucket)}"),
        executor.run(f'{bench_cfg} backup_region ""'),
        executor.run(f"{bench_cfg} backup_endpoint {shlex.quote(cfg.backup_s3_endpoint)}"),
        executor.run(f"{bench_cfg} backup_access_key {shlex.quote(cfg.backup_s3_access_key)}"),
        executor.run(f"{bench_cfg} backup_secret_key {shlex.quote(cfg.backup_s3_secret_key)}"),
    ]:
        if code != 0:
            failed = True
    if failed:
        fail(t("steps.site.backup_failed"))
    else:
        ok(t("steps.site.backup_configured"))


def _verify_health(cfg: Config, executor, compose_cmd: str):
    """Final health verification -- check site is accessible."""
    console.print()
    step(t("steps.site.verifying_health"))
    site_q = shlex.quote(cfg.site_name)
    code = executor.run(
        f"{compose_cmd} exec -T backend bench --site {site_q} doctor"
    )
    if code == 0:
        ok(t("steps.site.health_ok"))
    else:
        info(t("steps.site.health_warning"))


def _update_hosts(cfg: Config):
    """Add site to hosts file if needed (local mode only)."""
    if cfg.deploy_mode != "local":
        return

    console.print()
    console.print(Rule(t("steps.site.hosts_header"), style=ACCENT))
    console.print()

    hosts_path = (
        r"C:\Windows\System32\drivers\etc\hosts"
        if platform.system() == "Windows"
        else "/etc/hosts"
    )

    try:
        with open(hosts_path, "r") as f:
            hosts_content = f.read()

        if f"127.0.0.1 {cfg.site_name}" not in hosts_content:
            step(t("steps.site.hosts_adding", site_name=cfg.site_name))
            with open(hosts_path, "a") as f:
                f.write(f"\n127.0.0.1 {cfg.site_name}\n")
            ok(t("steps.site.hosts_updated"))
        else:
            ok(t("steps.site.hosts_exists"))
    except PermissionError:
        site_escaped = cfg.site_name.replace("[", "\\[")
        console.print(
            Panel(
                f"[bold {WARN}]{t('steps.site.hosts_permission_error')}[/]\n\n"
                f"{t('steps.site.hosts_manual')}\n"
                f"  [bold]{t('steps.site.hosts_file_label')}[/] : {hosts_path}\n"
                f"  [bold]{t('steps.site.hosts_line_label')}[/] : [cyan]127.0.0.1 {site_escaped}[/]",
                title=t("steps.site.hosts_perm_title"),
                title_align="left",
                border_style=WARN,
                padding=(1, 2),
            )
        )


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

    if cfg.enable_portainer:
        portainer_url = f"https://{cfg.domain}:9443" if cfg.deploy_mode != "local" else "https://localhost:9443"
        result_table.add_row(f"\U0001f5a5\ufe0f  {t('steps.site.done_portainer')}", portainer_url)

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

    step_header(5, TOTAL_STEPS, t("steps.site.title"))
    _create_site(cfg, executor, compose_cmd)

    for extra in cfg.extra_sites:
        _create_extra_site(extra, cfg, executor, compose_cmd)

    installed = (
        _install_extra_apps(cfg, executor, compose_cmd)
        + _install_community_apps(cfg, executor, compose_cmd)
        + _install_custom_apps(cfg, executor, compose_cmd)
    )

    # Install the same apps on extra sites (apps are already fetched,
    # just need install-app per site)
    for extra in cfg.extra_sites:
        site_q = shlex.quote(extra["name"])
        for app_name in cfg.extra_apps:
            executor.run(
                f"{compose_cmd} exec -T backend bench --site {site_q} "
                f"install-app {shlex.quote(app_name)}"
            )
        for app in cfg.community_apps:
            executor.run(
                f"{compose_cmd} exec -T backend bench --site {site_q} "
                f"install-app {shlex.quote(app.repo_name)}"
            )
        for app in cfg.custom_apps:
            executor.run(
                f"{compose_cmd} exec -T backend bench --site {site_q} "
                f"install-app {shlex.quote(app['name'])}"
            )

    if installed > 0:
        code = executor.run(f"{compose_cmd} restart frontend")
        if code != 0:
            fail(t("steps.site.frontend_restart_failed"))
    _configure_smtp(cfg, executor, compose_cmd)
    _configure_backup(cfg, executor, compose_cmd)
    _verify_health(cfg, executor, compose_cmd)
    _update_hosts(cfg)
    _show_done(cfg)
