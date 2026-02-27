"""UI primitives: banner, step headers, status messages, progress bar."""

import time

from rich.align import Align
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.rule import Rule
from rich.text import Text
from rich import box

from .theme import console, ACCENT, OK, ERR, WARN, MUTED, HEADING, BRAND
from .i18n import t


# ── Banner ───────────────────────────────────────────────────

def banner():
    """Print the startup splash banner."""
    W = 58  # inner width between ║…║

    lines = [
        ("", ACCENT),
        ("███████╗██████╗ ██████╗ ███╗   ██╗███████╗██╗  ██╗████████╗", BRAND),
        ("██╔════╝██╔══██╗██╔══██╗████╗  ██║██╔════╝╚██╗██╔╝╚══██╔══╝", BRAND),
        ("█████╗  ██████╔╝██████╔╝██╔██╗ ██║█████╗   ╚███╔╝    ██║   ", BRAND),
        ("██╔══╝  ██╔══██╗██╔═══╝ ██║╚██╗██║██╔══╝   ██╔██╗    ██║   ", BRAND),
        ("███████╗██║  ██║██║     ██║ ╚████║███████╗██╔╝ ██╗   ██║   ", BRAND),
        ("╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝   ╚═╝   ", BRAND),
        ("", ACCENT),
        (t("banner.subtitle"), "bright_white"),
        (t("banner.powered_by"), MUTED),
        ("", ACCENT),
    ]

    art = Text()
    art.append(f"╔{'═' * W}╗\n", style=ACCENT)
    for content, style in lines:
        art.append("║", style=ACCENT)
        art.append(f"{content:^{W}}", style=style)
        art.append("║\n", style=ACCENT)
    art.append(f"╚{'═' * W}╝", style=ACCENT)

    console.print(Align.center(art))
    console.print()


# ── Step header ──────────────────────────────────────────────

def step_header(step_num: int, total: int, title: str):
    """Render a step header with dot-progress subtitle."""
    dots = "● " * step_num + "○ " * (total - step_num)
    progress_text = Text(dots.strip(), style=ACCENT)

    console.print()
    console.print(Rule(style=ACCENT))
    console.print(
        Panel(
            Align.center(
                Text.assemble(
                    (f"{t('common.step_label')} {step_num}/{total}", HEADING),
                    ("  —  ", MUTED),
                    (title, "bold white"),
                )
            ),
            subtitle=progress_text,
            subtitle_align="center",
            box=box.DOUBLE_EDGE,
            border_style=ACCENT,
            padding=(1, 4),
        )
    )
    console.print()


# ── Status messages ──────────────────────────────────────────

def step(text: str):
    console.print(f"  [bold {ACCENT}]⟐[/]  {text}")


def ok(text: str):
    console.print(f"  [bold {OK}]✔[/]  [green]{text}[/green]")


def fail(text: str):
    console.print(f"  [bold {ERR}]✘[/]  [red]{text}[/red]")


def info(text: str):
    console.print(f"  [{MUTED}]   ↳ {text}[/]")


# ── Progress bar ─────────────────────────────────────────────

def animated_wait(seconds: int, message: str | None = None):
    """Rich progress bar with spinner while waiting."""
    if message is None:
        message = t("common.waiting")
    with Progress(
        SpinnerColumn("dots", style=f"bold {ACCENT}"),
        TextColumn(f"[bold white]{message}[/]"),
        BarColumn(bar_width=40, style=MUTED, complete_style=ACCENT, finished_style=OK),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as progress:
        task = progress.add_task(message, total=seconds)
        for _ in range(seconds):
            time.sleep(1)
            progress.advance(task, 1)
    ok(t("common.done"))
