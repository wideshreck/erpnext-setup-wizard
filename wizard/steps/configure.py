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
from ..prompts import ask_field, ask_password_field, ask_version_field, ask_apps_field, ask_select_field, confirm_action
from ..apps import OPTIONAL_APPS
from ..community_apps import CommunityApp, fetch_community_apps
from ..i18n import t
from ..versions import fetch_erpnext_versions
from . import TOTAL_STEPS


@dataclass
class Config:
    """Holds all user-supplied configuration values."""
    # Core
    deploy_mode: str = "local"
    site_name: str = ""
    erpnext_version: str = ""
    db_type: str = "mariadb"
    http_port: str = "8080"
    db_password: str = ""
    admin_password: str = ""
    extra_apps: list[str] = field(default_factory=list)
    community_apps: list[CommunityApp] = field(default_factory=list)
    custom_apps: list[dict] = field(default_factory=list)

    # Production + Remote
    domain: str = ""
    letsencrypt_email: str = ""

    # Remote SSH
    ssh_host: str = ""
    ssh_user: str = "root"
    ssh_port: int = 22
    ssh_key_path: str = ""

    # Optional: SMTP
    smtp_host: str = ""
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


def _validate_port(val: str) -> bool | str:
    if val.isdigit() and val == str(int(val)) and 1024 <= int(val) <= 65535:
        return True
    return t("steps.configure.port_invalid")


def _validate_site_name(val: str) -> bool | str:
    if re.fullmatch(r"[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)+", val):
        return True
    return t("steps.configure.site_name_invalid")


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

        n = 1  # dynamic field counter

        # ── 1. Deploy mode ────────────────────────────────────
        deploy_mode = ask_select_field(
            number=n,
            icon="🚀",
            label=t("steps.configure.deploy_mode"),
            choices=[
                ("local", t("steps.configure.deploy_local")),
                ("production", t("steps.configure.deploy_production")),
                ("remote", t("steps.configure.deploy_remote")),
            ],
            hint=t("steps.configure.deploy_mode_hint"),
        )
        n += 1

        # ── 2. SSH details (remote only) ─────────────────────
        ssh_host = ""
        ssh_user = "root"
        ssh_port_val = 22
        ssh_key_path = ""

        if deploy_mode == "remote":
            console.print(Rule(style="dim"))
            console.print()

            ssh_host = ask_field(
                number=n, icon="🖥️",
                label=t("steps.configure.ssh_host"),
                hint=t("steps.configure.ssh_host_hint"),
                examples="192.168.1.100 · server.example.com",
            )
            n += 1

            ssh_user = ask_field(
                number=n, icon="👤",
                label=t("steps.configure.ssh_user"),
                hint=t("steps.configure.ssh_user_hint"),
                default="root",
            )
            n += 1

            ssh_port_str = ask_field(
                number=n, icon="🔌",
                label=t("steps.configure.ssh_port"),
                hint=t("steps.configure.ssh_port_hint"),
                default="22",
                validate=_validate_ssh_port,
            )
            ssh_port_val = int(ssh_port_str)
            n += 1

            ssh_key_path = ask_field(
                number=n, icon="🔑",
                label=t("steps.configure.ssh_key"),
                hint=t("steps.configure.ssh_key_hint"),
                examples="~/.ssh/id_rsa · ~/.ssh/id_ed25519",
            )
            n += 1

        # ── 3. Site name ─────────────────────────────────────
        console.print(Rule(style="dim"))
        console.print()

        default_site = "mysite.localhost" if deploy_mode == "local" else "erp.example.com"
        site_name = ask_field(
            number=n,
            icon="🌐",
            label=t("steps.configure.site_name"),
            hint=t("steps.configure.site_name_hint"),
            examples="spaceflow.localhost · erp.localhost · myapp.localhost" if deploy_mode == "local"
                     else "erp.example.com · myapp.yourdomain.com",
            default=default_site,
            validate=_validate_site_name,
        )
        n += 1

        # ── 4. ERPNext version ───────────────────────────────
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
            number=n,
            icon="📦",
            label=t("steps.configure.erpnext_version"),
            hint=t("steps.configure.erpnext_version_hint"),
            choices=versions,
            default=default_version,
        )
        n += 1

        # ── 5. DB type ───────────────────────────────────────
        db_type = ask_select_field(
            number=n,
            icon="🗄️",
            label=t("steps.configure.db_type"),
            choices=[
                ("mariadb", "MariaDB"),
                ("postgres", "PostgreSQL"),
            ],
            hint=t("steps.configure.db_type_hint"),
        )
        n += 1

        # ── 6. HTTP port (local) OR domain + email (prod/remote) ──
        http_port = "8080"
        domain = ""
        letsencrypt_email = ""

        if deploy_mode == "local":
            http_port = ask_field(
                number=n,
                icon="🔌",
                label=t("steps.configure.http_port"),
                hint=t("steps.configure.http_port_hint"),
                default="8080",
                validate=_validate_port,
            )
            n += 1
        else:
            domain = ask_field(
                number=n,
                icon="🌍",
                label=t("steps.configure.domain"),
                hint=t("steps.configure.domain_hint"),
                examples="erp.example.com · myapp.yourdomain.com",
                validate=_validate_domain,
            )
            n += 1

            letsencrypt_email = ask_field(
                number=n,
                icon="📧",
                label=t("steps.configure.letsencrypt_email"),
                hint=t("steps.configure.letsencrypt_email_hint"),
                validate=_validate_email,
            )
            n += 1

        # ── 7. Passwords ─────────────────────────────────────
        console.print(Rule(style="dim"))
        console.print()

        db_password = ask_password_field(
            number=n,
            icon="🔒",
            label=t("steps.configure.db_password"),
        )
        n += 1

        admin_password = ask_password_field(
            number=n,
            icon="🔑",
            label=t("steps.configure.admin_password"),
        )
        n += 1

        # ── 8. Optional apps ─────────────────────────────────
        console.print(Rule(style="dim"))
        console.print()

        app_choices = [
            (app.repo_name, f"{app.display_name} — {t(app.i18n_key)}")
            for app in OPTIONAL_APPS
        ]

        extra_apps = ask_apps_field(
            number=n,
            icon="📦",
            label=t("steps.configure.extra_apps"),
            choices=app_choices,
        )
        n += 1

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
                number=n,
                icon="🌐",
                label=t("steps.configure.community_apps"),
                choices=community_choices,
                hint_key="steps.configure.community_apps_hint",
                none_key="steps.configure.community_apps_none",
                selected_key="steps.configure.community_apps_selected",
            )
            n += 1

            # Map selected repo_names back to full CommunityApp objects
            selected_set = set(selected_community)
            community_apps = [
                app for app in community_app_list if app.repo_name in selected_set
            ]
        else:
            fail(t("steps.configure.community_apps_failed"))

        # ── Custom private apps ──────────────────────────────
        console.print(Rule(style="dim"))
        console.print()

        custom_apps = []
        if confirm_action(t("steps.configure.custom_apps_prompt")):
            while True:
                url = ask_field(
                    number=n, icon="🔧",
                    label=t("steps.configure.custom_app_url"),
                    hint=t("steps.configure.custom_app_url_hint"),
                    examples="https://github.com/myorg/myapp.git",
                )
                if not url:
                    break
                branch = ask_field(
                    number=n, icon="🌿",
                    label=t("steps.configure.custom_app_branch"),
                    default="main",
                )
                n += 1
                # Extract repo_name from URL
                name = url.rstrip("/").rstrip(".git").split("/")[-1]
                custom_apps.append({"url": url, "branch": branch, "name": name})
                if not confirm_action(t("steps.configure.custom_app_add_another")):
                    break

        # ── 9. SMTP config (production/remote only) ──────────
        smtp_host = ""
        smtp_port = 587
        smtp_user = ""
        smtp_password = ""
        smtp_use_tls = True

        if deploy_mode != "local":
            console.print(Rule(style="dim"))
            console.print()

            if confirm_action(t("steps.configure.smtp_configure")):
                console.print()
                smtp_host = ask_field(
                    number=n, icon="📧",
                    label=t("steps.configure.smtp_host"),
                    hint=t("steps.configure.smtp_host_hint"),
                    examples="smtp.gmail.com · mail.example.com",
                )
                n += 1

                smtp_port_str = ask_field(
                    number=n, icon="🔌",
                    label=t("steps.configure.smtp_port"),
                    hint=t("steps.configure.smtp_port_hint"),
                    default="587",
                    validate=_validate_port,
                )
                smtp_port = int(smtp_port_str)
                n += 1

                smtp_user = ask_field(
                    number=n, icon="👤",
                    label=t("steps.configure.smtp_user"),
                    hint=t("steps.configure.smtp_user_hint"),
                )
                n += 1

                smtp_password = ask_password_field(
                    number=n, icon="🔒",
                    label=t("steps.configure.smtp_password"),
                    min_length=1,
                )
                n += 1

                smtp_use_tls = confirm_action(t("steps.configure.smtp_use_tls"))

        # ── 10. Backup config (production/remote only) ───────
        backup_enabled = False
        backup_s3_endpoint = ""
        backup_s3_bucket = ""
        backup_s3_access_key = ""
        backup_s3_secret_key = ""

        if deploy_mode != "local":
            console.print(Rule(style="dim"))
            console.print()

            if confirm_action(t("steps.configure.backup_configure")):
                backup_enabled = True
                console.print()

                backup_s3_endpoint = ask_field(
                    number=n, icon="☁️",
                    label=t("steps.configure.backup_s3_endpoint"),
                    hint=t("steps.configure.backup_s3_endpoint_hint"),
                    examples="s3.amazonaws.com · minio.example.com",
                )
                n += 1

                backup_s3_bucket = ask_field(
                    number=n, icon="🪣",
                    label=t("steps.configure.backup_s3_bucket"),
                    hint=t("steps.configure.backup_s3_bucket_hint"),
                )
                n += 1

                backup_s3_access_key = ask_field(
                    number=n, icon="🔑",
                    label=t("steps.configure.backup_s3_access_key"),
                    hint=t("steps.configure.backup_s3_access_key_hint"),
                )
                n += 1

                backup_s3_secret_key = ask_password_field(
                    number=n, icon="🔒",
                    label=t("steps.configure.backup_s3_secret_key"),
                    min_length=1,
                )
                n += 1

        # ── 11. Summary table ────────────────────────────────
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

        table.add_row(f"🚀  {t('steps.configure.deploy_mode')}", deploy_mode)
        table.add_row(f"🌐  {t('steps.configure.site_name')}", site_name)
        table.add_row(f"📦  {t('steps.configure.erpnext_version')}", erpnext_version)
        table.add_row(f"🗄️  {t('steps.configure.db_type')}", db_type)

        if deploy_mode == "local":
            table.add_row(f"🔌  {t('steps.configure.http_port')}", http_port)
        else:
            table.add_row(f"🌍  {t('steps.configure.domain')}", domain)
            table.add_row(f"📧  {t('steps.configure.letsencrypt_email')}", letsencrypt_email)

        if deploy_mode == "remote":
            table.add_row(f"🖥️  {t('steps.configure.ssh_host')}", ssh_host)

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

        if custom_apps:
            custom_display = ", ".join(app["name"] for app in custom_apps)
        else:
            custom_display = "—"
        table.add_row(f"🔧  {t('steps.configure.custom_apps_label')}", custom_display)

        if smtp_host:
            table.add_row(f"📧  {t('steps.configure.smtp_host')}", smtp_host)
        if backup_enabled:
            table.add_row(f"☁️  {t('steps.configure.backup_s3_endpoint')}", backup_s3_endpoint)

        console.print(Align.center(table))
        console.print()

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
                custom_apps=custom_apps,
                domain=domain,
                letsencrypt_email=letsencrypt_email,
                ssh_host=ssh_host,
                ssh_user=ssh_user,
                ssh_port=ssh_port_val,
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

        # User declined — ask if they want to re-enter
        if not confirm_action(t("steps.configure.confirm_declined")):
            console.print(Panel(f"[yellow]{t('steps.configure.cancelled')}[/yellow]", border_style=WARN))
            sys.exit(0)

        console.print()
