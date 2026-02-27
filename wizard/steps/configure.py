"""Step 2: Gather configuration from the user."""

import sys
from dataclasses import dataclass

from rich.panel import Panel
from rich.table import Table
from rich.align import Align
from rich.rule import Rule
from rich import box

from ..theme import console, ACCENT, HEADING, WARN, MUTED
from ..ui import step_header
from ..prompts import ask_field, ask_password_field, confirm_action
from ..i18n import t
from . import TOTAL_STEPS


@dataclass
class Config:
    """Holds all user-supplied configuration values."""
    site_name: str
    erpnext_version: str
    http_port: str
    db_password: str
    admin_password: str


def run_configure() -> Config:
    """Prompt for configuration and return a Config dataclass."""
    step_header(2, TOTAL_STEPS, t("steps.configure.title"))

    console.print(
        Panel(
            f"[dim]{t('steps.configure.intro')}[/dim]",
            box=box.ROUNDED,
            border_style=MUTED,
            padding=(0, 2),
        )
    )
    console.print()

    site_name = ask_field(
        number=1,
        icon="🌐",
        label=t("steps.configure.site_name"),
        hint=t("steps.configure.site_name_hint"),
        examples="spaceflow.localhost · erp.localhost · myapp.localhost",
        default="mysite.localhost",
    )

    erpnext_version = ask_field(
        number=2,
        icon="📦",
        label=t("steps.configure.erpnext_version"),
        hint=t("steps.configure.erpnext_version_hint"),
        default="v16.7.3",
    )

    http_port = ask_field(
        number=3,
        icon="🔌",
        label=t("steps.configure.http_port"),
        hint=t("steps.configure.http_port_hint"),
        default="8080",
    )

    console.print(Rule(style="dim"))
    console.print()

    db_password = ask_password_field(
        number=4,
        icon="🔒",
        label=t("steps.configure.db_password"),
    )

    admin_password = ask_password_field(
        number=5,
        icon="🔑",
        label=t("steps.configure.admin_password"),
    )

    # ── Summary table ────────────────────────────────────────
    console.print()
    table = Table(
        title=t("steps.configure.summary_title"),
        box=box.DOUBLE_EDGE,
        border_style=ACCENT,
        title_style=HEADING,
        header_style="bold bright_white",
        padding=(0, 2),
        show_lines=True,
    )
    table.add_column(t("steps.configure.col_setting"), style="white", min_width=22)
    table.add_column(t("steps.configure.col_value"), style=f"bold {ACCENT}", min_width=28)

    table.add_row(f"🌐  {t('steps.configure.site_name')}", site_name)
    table.add_row(f"📦  {t('steps.configure.erpnext_version')}", erpnext_version)
    table.add_row(f"🔌  {t('steps.configure.http_port')}", http_port)
    table.add_row(f"🔒  {t('steps.configure.db_password')}", "•" * len(db_password))
    table.add_row(f"🔑  {t('steps.configure.admin_password')}", "•" * len(admin_password))

    console.print(Align.center(table))
    console.print()

    if not confirm_action(t("steps.configure.confirm")):
        console.print(Panel(f"[yellow]{t('steps.configure.cancelled')}[/yellow]", border_style=WARN))
        sys.exit(0)

    return Config(
        site_name=site_name,
        erpnext_version=erpnext_version,
        http_port=http_port,
        db_password=db_password,
        admin_password=admin_password,
    )
