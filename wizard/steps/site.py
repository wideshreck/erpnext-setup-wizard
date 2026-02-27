"""Step 5: Create ERPNext site, configure hosts, show completion."""

import platform
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
from ..utils import run
from .configure import Config
from ..i18n import t
from . import TOTAL_STEPS


def _create_site(cfg: Config):
    """Create the ERPNext site via bench."""
    site_escaped = cfg.site_name.replace("[", "\\[")
    step(t("steps.site.creating", site_name=site_escaped))
    info(t("steps.site.creating_hint"))

    code = run(
        f"docker compose exec backend bench new-site {cfg.site_name} "
        f"--install-app erpnext "
        f"--db-root-password {cfg.db_password} "
        f"--admin-password {cfg.admin_password}"
    )
    if code != 0:
        fail(t("steps.site.create_failed"))
        sys.exit(1)
    ok(t("steps.site.created"))

    console.print()
    step(t("steps.site.enabling_scheduler"))
    run(f"docker compose exec backend bench --site {cfg.site_name} enable-scheduler")
    ok(t("steps.site.scheduler_enabled"))


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

        if cfg.site_name not in hosts_content:
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
    """Step 5: create site, update hosts, show done."""
    step_header(5, TOTAL_STEPS, t("steps.site.title"))
    _create_site(cfg)
    _update_hosts(cfg)
    _show_done(cfg)
