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
    if getattr(args, "ssh_host", None):
        executor = SSHExecutor(
            host=args.ssh_host,
            user=getattr(args, "ssh_user", None) or "root",
            port=getattr(args, "ssh_port", None) or 22,
            key_path=getattr(args, "ssh_key", None) or "",
        )
        project_dir = f"~/{getattr(args, 'project', 'frappe_docker')}"
        cd_prefix = f"cd {project_dir} && "
    else:
        executor = LocalExecutor()
        cd_prefix = ""

    # Get container status
    result = executor.run(f"{cd_prefix}docker compose ps --format json", capture=True)
    code, stdout, _ = result

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
        if not line.strip():
            continue
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

    console.print()
    console.print(table)

    # Show current version from .env
    result = executor.run(f"{cd_prefix}cat .env", capture=True)
    code, stdout, _ = result
    if code == 0:
        for line in stdout.split("\n"):
            if line.startswith("ERPNEXT_VERSION="):
                version = line.split("=", 1)[1].strip().strip('"')
                console.print(f"\n  ERPNext: [bold {ACCENT}]{version}[/]")
    console.print()
