#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["rich>=13.9.0", "questionary>=2.1.0", "pyyaml>=6.0"]
# ///
"""
ERPNext Setup Wizard — frappe_docker
Premium terminal UI powered by Rich + questionary

Usage:
    uv run erpnext-setup-wizard.py                        # interactive setup (default)
    uv run erpnext-setup-wizard.py setup                  # explicit setup subcommand
    uv run erpnext-setup-wizard.py --lang en              # setup with language preset
    uv run erpnext-setup-wizard.py setup --config deploy.yml
    uv run erpnext-setup-wizard.py upgrade --version v16.8.0
    uv run erpnext-setup-wizard.py exec
    uv run erpnext-setup-wizard.py status
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


# ── Subcommand handlers ────────────────────────────────────────


def _run_setup(args, lang: str) -> None:
    """Run the interactive (or unattended) setup wizard."""
    unattended_cfg = load_config(args)

    if not unattended_cfg and not args.lang:
        clear_screen()
        lang = select_language()

    i18n_init(lang)

    if not unattended_cfg:
        clear_screen()
        banner()

    # Configuration (interactive or unattended)
    if unattended_cfg:
        cfg = unattended_cfg
    else:
        cfg = run_configure()

    executor = create_executor(cfg)

    run_prerequisites(cfg, executor)
    run_env_file(cfg, executor)
    run_docker(cfg, executor)
    run_site(cfg, executor)


def _run_upgrade(args, lang: str) -> None:
    """Upgrade an existing ERPNext installation."""
    from wizard.commands.upgrade import run_upgrade
    i18n_init(lang)
    run_upgrade(args)


def _run_exec(args, lang: str) -> None:
    """Execute a command in a running container."""
    from wizard.commands.exec_cmd import run_exec
    run_exec(args)


def _run_status(args, lang: str) -> None:
    """Show status of the ERPNext stack."""
    from wizard.commands.status import run_status
    i18n_init(lang)
    run_status(args)


# ── Main dispatch ───────────────────────────────────────────────


def main():
    parser = build_parser()
    args = parser.parse_args()

    # --lang can appear on root parser or subparser.
    # When subparser also defines --lang, argparse may override the root value.
    # Use parse_known_args to detect if root parser captured --lang.
    lang = getattr(args, "lang", None) or "en"

    # Default to setup when no subcommand is given
    command = args.command or "setup"

    if command == "setup":
        _run_setup(args, lang)
    elif command == "upgrade":
        _run_upgrade(args, lang)
    elif command == "exec":
        _run_exec(args, lang)
    elif command == "status":
        _run_status(args, lang)
    else:
        parser.print_help()
        sys.exit(1)


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
