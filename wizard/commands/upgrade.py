"""Upgrade an existing ERPNext installation to a new version."""

import shlex

from ..theme import console
from ..ui import step, ok, fail, info, banner
from ..utils import version_branch
from ..versions import fetch_erpnext_versions
from ..prompts import ask_version_field, confirm_action
from ..ssh import LocalExecutor, SSHExecutor
from ..i18n import t


def _read_current_env(executor, project_dir: str) -> dict:
    """Read current .env values."""
    result = executor.run(f"cat {project_dir}/.env", capture=True)
    code, stdout, _ = result
    if code != 0:
        return {}
    env = {}
    for line in stdout.strip().split("\n"):
        if "=" in line and not line.startswith("#"):
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip('"')
    return env


def run_upgrade(args):
    """Execute the upgrade workflow."""
    banner()

    # Determine executor
    if getattr(args, "ssh_host", None):
        executor = SSHExecutor(
            host=args.ssh_host,
            user=getattr(args, "ssh_user", None) or "root",
            port=getattr(args, "ssh_port", None) or 22,
            key_path=getattr(args, "ssh_key", None) or "",
        )
        is_remote = True
    else:
        executor = LocalExecutor()
        is_remote = False

    project = getattr(args, "project", "frappe_docker")
    project_dir = f"~/{project}" if is_remote else project
    cd_prefix = f"cd {project_dir} && " if is_remote else ""

    # Step 1: Read current version
    step(t("commands.upgrade.reading_env"))
    env = _read_current_env(executor, project_dir)
    current_version = env.get("ERPNEXT_VERSION", "unknown")
    ok(t("commands.upgrade.current_version", version=current_version))

    # Step 2: Select target version
    if getattr(args, "version", None):
        target_version = args.version
    else:
        console.print()
        info(t("commands.upgrade.fetching_versions"))
        versions = fetch_erpnext_versions()
        target_version = ask_version_field(
            1, "\U0001f504", t("commands.upgrade.select_version"),
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
    console.print()
    step(t("commands.upgrade.backing_up"))
    executor.run(f"{cd_prefix}docker compose exec -T backend bench --site all backup")
    ok(t("commands.upgrade.backup_done"))

    # Step 4: Update .env
    console.print()
    step(t("commands.upgrade.updating_env"))
    new_frappe = version_branch(target_version)
    executor.run(
        f"{cd_prefix}sed -i "
        f"'s/ERPNEXT_VERSION=.*/ERPNEXT_VERSION={shlex.quote(target_version)}/' .env"
    )
    executor.run(
        f"{cd_prefix}sed -i "
        f"'s/FRAPPE_VERSION=.*/FRAPPE_VERSION={shlex.quote(new_frappe)}/' .env"
    )
    ok(t("commands.upgrade.env_updated"))

    # Step 5: Pull new images and restart
    console.print()
    step(t("commands.upgrade.pulling_images"))
    executor.run(f"{cd_prefix}docker compose pull")
    ok(t("commands.upgrade.images_pulled"))

    console.print()
    step(t("commands.upgrade.restarting"))
    executor.run(f"{cd_prefix}docker compose up -d")
    ok(t("commands.upgrade.restarted"))

    # Step 6: Run migrate
    console.print()
    step(t("commands.upgrade.migrating"))
    code = executor.run(f"{cd_prefix}docker compose exec -T backend bench --site all migrate")
    if code == 0:
        ok(t("commands.upgrade.migrate_done"))
    else:
        fail(t("commands.upgrade.migrate_failed"))

    console.print()
    ok(t("commands.upgrade.complete", version=target_version))
