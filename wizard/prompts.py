"""Interactive prompts powered by questionary + Rich headers."""

import re
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


def ask_version_field(
    number: int,
    icon: str,
    label: str,
    hint: str = "",
    choices: list[str] | None = None,
    default: str = "",
) -> str:
    """Autocomplete version selector using questionary.autocomplete.

    If choices is empty/None, falls back to ask_field with validation.
    """
    def _validate_version_format(val: str) -> bool | str:
        if re.fullmatch(r"v\d+\.\d+\.\d+", val):
            return True
        return t("steps.configure.version_invalid")

    if not choices:
        return ask_field(
            number=number, icon=icon, label=label, hint=hint,
            default=default,
            validate=_validate_version_format,
        )

    _field_header(number, icon, label)

    if hint:
        console.print(f"      [{MUTED}]{hint}[/]")
    console.print(f"      [{MUTED}]{t('steps.configure.version_search_hint')}[/]")

    choices_set = set(choices)

    def _validate_in_list(val: str) -> bool | str:
        if val in choices_set:
            return True
        return t("steps.configure.version_invalid")

    value = questionary.autocomplete(
        message="",
        choices=choices,
        default=default,
        qmark="      ▸",
        style=Q_STYLE,
        match_middle=True,
        ignore_case=True,
        validate=_validate_in_list,
    ).ask()

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
    """Password field with confirmation and inline validation."""
    _field_header(number, icon, label)
    console.print(f"      [{MUTED}]{t('prompts.password_min_hint', min_length=min_length)}[/]")
    console.print(f"      [{MUTED}]{t('steps.configure.password_chars_warning')}[/]")

    def _validate(val: str) -> bool | str:
        if len(val) >= min_length:
            return True
        return t("prompts.password_too_short", min_length=min_length)

    while True:
        password = questionary.password(
            message="",
            qmark="      ▸",
            style=Q_STYLE,
            validate=_validate,
        ).ask()

        if password is None:
            _cancelled()

        # Confirmation
        console.print(f"      [{MUTED}]{t('prompts.password_confirm')}[/]")
        confirm = questionary.password(
            message="",
            qmark="      ▸",
            style=Q_STYLE,
        ).ask()

        if confirm is None:
            _cancelled()

        if password == confirm:
            break

        console.print(f"      [bold {ERR}]✘[/] [{ERR}]{t('prompts.password_mismatch')}[/]")
        console.print()

    console.print(f"      [bold {OK}]✔[/] [green]{t('prompts.password_accepted')}[/green]  [{MUTED}]({'•' * 8})[/]")
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
