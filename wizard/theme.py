"""Shared console instance, color constants, and questionary style."""

import questionary
from questionary import Style as QStyle
from rich.console import Console

# ── Console (single instance used everywhere) ────────────────
console = Console()

# ── Rich color tokens ────────────────────────────────────────
ACCENT  = "cyan"
OK      = "green"
WARN    = "yellow"
ERR     = "red"
MUTED   = "dim white"
HEADING = "bold cyan"
BRAND   = "bold bright_cyan"

# ── Questionary prompt style ─────────────────────────────────
Q_STYLE = QStyle([
    ("qmark",       "fg:ansicyan bold"),
    ("question",    "fg:ansiwhite bold"),
    ("answer",      "fg:ansicyan bold"),
    ("pointer",     "fg:ansicyan bold"),
    ("highlighted", "fg:ansicyan bold"),
    ("selected",    "fg:ansicyan"),
    ("instruction", "fg:ansibrightblack"),
    ("text",        "fg:ansiwhite"),
])
