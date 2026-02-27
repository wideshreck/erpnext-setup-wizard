#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["rich>=13.9.0", "questionary>=2.1.0", "pyyaml>=6.0"]
# ///
"""
ERPNext Setup Wizard — frappe_docker
Premium terminal UI powered by Rich + questionary

Usage:
    uv run erpnext-setup-wizard.py
    uv run erpnext-setup-wizard.py --lang en
    uv run erpnext-setup-wizard.py --config deploy.yml
    uv run erpnext-setup-wizard.py --mode production --site-name erp.example.com ...
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


def main():
    parser = build_parser()
    args = parser.parse_args()

    lang = args.lang or "en"
    unattended_cfg = load_config(args)

    if not unattended_cfg and not args.lang:
        clear_screen()
        lang = select_language()

    i18n_init(lang)

    if not unattended_cfg:
        clear_screen()
        banner()

    # Step 2 — Configuration (interactive or unattended)
    if unattended_cfg:
        cfg = unattended_cfg
    else:
        cfg = run_configure()

    # Create executor based on deploy mode
    executor = create_executor(cfg)

    # Step 1 — Prerequisites
    run_prerequisites(cfg, executor)

    # Step 3 — .env File
    run_env_file(cfg, executor)

    # Step 4 — Docker Compose
    run_docker(cfg, executor)

    # Step 5 — Site Creation + Completion
    run_site(cfg, executor)


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
