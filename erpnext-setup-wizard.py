#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["rich>=13.9.0", "questionary>=2.1.0"]
# ///
"""
ERPNext Setup Wizard — frappe_docker
Premium terminal UI powered by Rich + questionary

Usage:
    uv run erpnext-setup-wizard.py
    uv run erpnext-setup-wizard.py --lang en
    uv run erpnext-setup-wizard.py --lang tr
"""

import argparse

from wizard.i18n import init as i18n_init, select_language
from wizard.ui import banner
from wizard.utils import clear_screen
from wizard.steps import (
    run_prerequisites,
    run_configure,
    run_env_file,
    run_docker,
    run_site,
)


def main():
    parser = argparse.ArgumentParser(description="ERPNext Setup Wizard")
    parser.add_argument("--lang", type=str, help="Language code (e.g., tr, en)")
    args = parser.parse_args()

    lang = args.lang
    if not lang:
        clear_screen()
        lang = select_language()

    i18n_init(lang)
    clear_screen()
    banner()

    # Step 1 — Prerequisites
    run_prerequisites()

    # Step 2 — Configuration
    cfg = run_configure()

    # Step 3 — .env File
    run_env_file(cfg)

    # Step 4 — Docker Compose
    run_docker()

    # Step 5 — Site Creation + Completion
    run_site(cfg)


if __name__ == "__main__":
    main()
