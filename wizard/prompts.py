"""Interactive prompts powered by questionary + Rich headers."""

import sys

import questionary
from rich.text import Text

from .theme import console, ACCENT, OK, WARN, ERR, MUTED, Q_STYLE
from .i18n import t

# ── Circled number badges ────────────────────────────────────
_FIELD_NUM = ["❶", "❷", "❸", "❹", "❺", "❻", "❼", "❽", "❾", "❿"]


def _field_header(number: int, icon: str, label: str):
    """Print the styled header line for a field card."""
    badge = _FIELD_NUM[number - 1] if number <= len(_FIELD_NUM) else f"({number})"
    console.print(
        Text.assemble(
            (f" {badge} ", f"bold {ACCENT}"),
            (f" {icon}  ", ""),
            (label, "bold bright_white"),
        )
    )


def _cancelled():
    console.print(f"\n  [{WARN}]{t('common.cancelled')}[/]")
    sys.exit(0)


# ── Public prompts ───────────────────────────────────────────

def ask_field(
    number: int,
    icon: str,
    label: str,
    hint: str = "",
    default: str = "",
    examples: str = "",
    validate=None,
) -> str:
    """Text input field with questionary."""
    _field_header(number, icon, label)

    if hint:
        console.print(f"      [{MUTED}]{hint}[/]")
    if examples:
        console.print(f"      [{MUTED}]{t('common.examples')}: [italic]{examples}[/italic][/]")

    kwargs = dict(
        message="",
        default=default,
        qmark="      ▸",
        style=Q_STYLE,
    )
    if validate is not None:
        kwargs["validate"] = validate
    value = questionary.text(**kwargs).ask()

    if value is None:
        _cancelled()

    console.print(f"      [bold {OK}]✔[/] [green]{value}[/green]")
    console.print()
    return value


def ask_password_field(
    number: int,
    icon: str,
    label: str,
    min_length: int = 6,
) -> str:
    """Password field with inline validation."""
    _field_header(number, icon, label)
    console.print(f"      [{MUTED}]{t('prompts.password_min_hint', min_length=min_length)}[/]")

    def _validate(val: str) -> bool | str:
        if len(val) >= min_length:
            return True
        return t("prompts.password_too_short", min_length=min_length)

    password = questionary.password(
        message="",
        qmark="      ▸",
        style=Q_STYLE,
        validate=_validate,
    ).ask()

    if password is None:
        _cancelled()

    console.print(f"      [bold {OK}]✔[/] [green]{t('prompts.password_accepted')}[/green]  [{MUTED}]({'•' * len(password)})[/]")
    console.print()
    return password


def confirm_action(question: str) -> bool:
    """Styled yes/no confirmation."""
    console.print()
    result = questionary.confirm(
        message=question,
        default=True,
        qmark="  ▸",
        style=Q_STYLE,
    ).ask()

    if result is None:
        _cancelled()
    return result
