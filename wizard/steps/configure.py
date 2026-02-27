"""Step 2: Gather configuration from the user."""

import re
import sys
from dataclasses import dataclass, field

from rich.panel import Panel
from rich.table import Table
from rich.align import Align
from rich.rule import Rule
from rich import box

from ..theme import console, ACCENT, HEADING, WARN, MUTED
from ..ui import step_header, step, ok, fail
from ..prompts import ask_field, ask_password_field, ask_version_field, ask_apps_field, confirm_action
from ..apps import OPTIONAL_APPS
from ..community_apps import CommunityApp, fetch_community_apps
from ..i18n import t
from ..versions import fetch_erpnext_versions
from . import TOTAL_STEPS


@dataclass
class Config:
    """Holds all user-supplied configuration values."""
    site_name: str
    erpnext_version: str
    http_port: str
    db_password: str
    admin_password: str
    extra_apps: list[str] = field(default_factory=list)
    community_apps: list[CommunityApp] = field(default_factory=list)


def _validate_port(val: str) -> bool | str:
    if val.isdigit() and val == str(int(val)) and 1024 <= int(val) <= 65535:
        return True
    return t("steps.configure.port_invalid")


def _validate_site_name(val: str) -> bool | str:
    if re.fullmatch(r"[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)+", val):
        return True
    return t("steps.configure.site_name_invalid")


def run_configure() -> Config:
    """Prompt for configuration and return a Config dataclass."""
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

        site_name = ask_field(
            number=1,
            icon="🌐",
            label=t("steps.configure.site_name"),
            hint=t("steps.configure.site_name_hint"),
            examples="spaceflow.localhost · erp.localhost · myapp.localhost",
            default="mysite.localhost",
            validate=_validate_site_name,
        )

        # Fetch available versions from GitHub
        step(t("steps.configure.fetching_versions"))
        versions = fetch_erpnext_versions()

        if versions:
            ok(t("steps.configure.versions_loaded", count=len(versions)))
            default_version = versions[0]  # newest stable
        else:
            fail(t("steps.configure.versions_failed"))
            versions = None
            default_version = "v16.7.3"

        console.print()

        erpnext_version = ask_version_field(
            number=2,
            icon="📦",
            label=t("steps.configure.erpnext_version"),
            hint=t("steps.configure.erpnext_version_hint"),
            choices=versions,
            default=default_version,
        )

        http_port = ask_field(
            number=3,
            icon="🔌",
            label=t("steps.configure.http_port"),
            hint=t("steps.configure.http_port_hint"),
            default="8080",
            validate=_validate_port,
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

        # ── Optional apps ───────────────────────────────────
        console.print(Rule(style="dim"))
        console.print()

        app_choices = [
            (app.repo_name, f"{app.display_name} — {t(app.i18n_key)}")
            for app in OPTIONAL_APPS
        ]

        extra_apps = ask_apps_field(
            number=6,
            icon="📦",
            label=t("steps.configure.extra_apps"),
            choices=app_choices,
        )

        # ── Community apps ───────────────────────────────────
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
                number=7,
                icon="🌐",
                label=t("steps.configure.community_apps"),
                choices=community_choices,
            )

            # Map selected repo_names back to full CommunityApp objects
            selected_set = set(selected_community)
            community_apps = [
                app for app in community_app_list if app.repo_name in selected_set
            ]
        else:
            fail(t("steps.configure.community_apps_failed"))

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
        table.add_row(f"🔒  {t('steps.configure.db_password')}", "••••••••")
        table.add_row(f"🔑  {t('steps.configure.admin_password')}", "••••••••")
        if extra_apps:
            apps_display = ", ".join(extra_apps)
        else:
            apps_display = "—"
        table.add_row(f"📦  {t('steps.configure.extra_apps')}", apps_display)
        if community_apps:
            community_display = ", ".join(app.display_name for app in community_apps)
        else:
            community_display = "—"
        table.add_row(f"🌐  {t('steps.configure.community_apps')}", community_display)

        console.print(Align.center(table))
        console.print()

        if confirm_action(t("steps.configure.confirm")):
            return Config(
                site_name=site_name,
                erpnext_version=erpnext_version,
                http_port=http_port,
                db_password=db_password,
                admin_password=admin_password,
                extra_apps=extra_apps,
                community_apps=community_apps,
            )

        # User declined — ask if they want to re-enter
        if not confirm_action(t("steps.configure.confirm_declined")):
            console.print(Panel(f"[yellow]{t('steps.configure.cancelled')}[/yellow]", border_style=WARN))
            sys.exit(0)

        console.print()
