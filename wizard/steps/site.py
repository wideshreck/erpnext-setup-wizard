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
from ..utils import run, version_branch
from ..apps import OPTIONAL_APPS, detect_best_branch
from .configure import Config
from ..i18n import t
from . import TOTAL_STEPS
from .docker import build_compose_cmd


def _create_site(cfg: Config, compose_cmd: str):
    """Create the ERPNext site via bench, with retry on failure."""
    from ..prompts import confirm_action

    site_escaped = cfg.site_name.replace("[", "\\[")
    step(t("steps.site.creating", site_name=site_escaped))
    info(t("steps.site.creating_hint"))

    while True:
        code = run(
            f"{compose_cmd} exec -T backend bench new-site {shlex.quote(cfg.site_name)} "
            f"--install-app erpnext "
            f"--db-root-password {shlex.quote(cfg.db_password)} "
            f"--admin-password {shlex.quote(cfg.admin_password)}"
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
    code = run(f"{compose_cmd} exec -T backend bench --site {shlex.quote(cfg.site_name)} enable-scheduler")
    if code != 0:
        fail(t("steps.site.scheduler_failed"))
    else:
        ok(t("steps.site.scheduler_enabled"))


def _install_app(repo_name: str, display_name: str, source: str,
                  branch: str, site_name: str, fail_key: str,
                  compose_cmd: str = "") -> bool:
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
    code = run(
        f"{compose_cmd} exec -T backend bench get-app "
        f"--branch {branch_q} {source_q}"
    )
    if code != 0:
        fail(t(fail_key, app=display_name))
        return False

    # Step 2: pip install (bench get-app skips this in production containers)
    code = run(f"{compose_cmd} exec -T backend pip install -e apps/{app_q}")
    if code != 0:
        fail(t(fail_key, app=display_name))
        return False

    # Step 3: Register in apps.txt if missing
    run(
        f"{compose_cmd} exec -T backend bash -c "
        f"'grep -qxF {app_q} sites/apps.txt || echo {app_q} >> sites/apps.txt'"
    )

    # Step 4: Install on site
    code = run(
        f"{compose_cmd} exec -T backend bench --site {site_q} "
        f"install-app {app_q}"
    )
    if code != 0:
        fail(t(fail_key, app=display_name))
        return False

    # Step 5: Build assets (CSS, JS, images)
    build_code = run(f"{compose_cmd} exec -T backend bench build --app {app_q}")
    if build_code != 0:
        fail(t("steps.site.app_build_failed", app=display_name))
        return False

    # Step 6: Copy assets to frontend container.
    # bench build creates a symlink sites/assets/{app} -> apps/{app}/.../public
    # but the frontend container doesn't have the apps/ volume, so the
    # symlink is dangling.  Replace it with the actual files.
    run(
        f"{compose_cmd} exec -T backend bash -c "
        f"'if [ -L sites/assets/{app_q} ]; then "
        f"target=$(readlink -f sites/assets/{app_q}) && "
        f"rm sites/assets/{app_q} && "
        f"cp -r \"$target\" sites/assets/{app_q}; fi'"
    )

    return True


def _install_extra_apps(cfg: Config, compose_cmd: str) -> int:
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
                        compose_cmd=compose_cmd):
            ok(t("steps.site.app_installed", app=app_name))
        else:
            failed.append(app_name)

    console.print()
    if failed:
        fail(t("steps.site.apps_some_failed", failed=len(failed), total=len(cfg.extra_apps)))
    else:
        ok(t("steps.site.apps_done", count=len(cfg.extra_apps)))

    return len(cfg.extra_apps) - len(failed)


def _install_community_apps(cfg: Config, compose_cmd: str) -> int:
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
                        compose_cmd=compose_cmd):
            ok(t("steps.site.community_app_installed", app=app.display_name))
        else:
            failed.append(app.display_name)

    console.print()
    if failed:
        fail(t("steps.site.community_apps_some_failed", failed=len(failed), total=len(cfg.community_apps)))
    else:
        ok(t("steps.site.community_apps_done", count=len(cfg.community_apps)))

    return len(cfg.community_apps) - len(failed)


def _update_hosts(cfg: Config):
    """Add site to hosts file if needed."""
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
    url = f"http://{cfg.site_name}:{cfg.http_port}"

    result_table = Table(box=box.SIMPLE_HEAVY, border_style=OK, padding=(0, 3), show_header=False)
    result_table.add_column(style="bold white")
    result_table.add_column(style=f"bold {ACCENT}")
    result_table.add_row("🌐  URL", url)
    result_table.add_row(f"👤  {t('steps.site.done_user')}", "Administrator")
    result_table.add_row(f"🔑  {t('steps.site.done_password')}", t("steps.site.done_password_hint"))

    done_title = Text.assemble(
        ("\n🎉  ", ""),
        (t("steps.site.done_title"), "bold bright_green"),
        ("\n", ""),
    )
    done_footer = Text(
        f"\n{t('steps.site.done_open_browser', url=url)}\n",
        style=MUTED,
    )

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


def run_site(cfg: Config):
    """Step 5: create site, install extra apps, update hosts, show done."""
    step_header(5, TOTAL_STEPS, t("steps.site.title"))
    compose_cmd = build_compose_cmd(cfg)
    _create_site(cfg, compose_cmd)
    installed = _install_extra_apps(cfg, compose_cmd) + _install_community_apps(cfg, compose_cmd)
    if installed > 0:
        run(f"{compose_cmd} restart frontend")
    _update_hosts(cfg)
    _show_done(cfg)
