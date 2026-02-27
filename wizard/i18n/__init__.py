"""Internationalization engine for the wizard."""

import json
import os

_translations: dict = {}


def _i18n_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _load_translations(lang: str) -> dict:
    filepath = os.path.join(_i18n_dir(), f"{lang}.json")
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def get_available_langs() -> list[dict]:
    """Return list of available languages: [{"code": "tr", "name": "Türkçe"}, ...]"""
    langs = []
    for f in sorted(os.listdir(_i18n_dir())):
        if f.endswith(".json"):
            code = f[:-5]
            data = _load_translations(code)
            langs.append({"code": code, "name": data.get("lang_name", code)})
    return langs


def init(lang: str):
    """Initialize i18n with the given language code."""
    global _translations
    filepath = os.path.join(_i18n_dir(), f"{lang}.json")
    if not os.path.exists(filepath):
        available = [l["code"] for l in get_available_langs()]
        raise SystemExit(
            f"Unknown language: '{lang}'. Available: {', '.join(available)}"
        )
    _translations = _load_translations(lang)


def t(key: str, **kwargs) -> str:
    """Translate a key using dot notation. Returns key itself if not found."""
    parts = key.split(".")
    value = _translations
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return key
    if not isinstance(value, str):
        return key
    if kwargs:
        try:
            return value.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return value
    return value


def select_language() -> str:
    """Show interactive language picker before i18n is initialized. Returns language code."""
    import questionary
    from ..theme import console, Q_STYLE
    from rich.text import Text

    langs = get_available_langs()
    choices = [
        questionary.Choice(title=lang["name"], value=lang["code"])
        for lang in langs
    ]

    console.print()
    console.print(
        Text.assemble(
            ("  🌐  ", ""),
            ("Select Language", "bold bright_white"),
            (" / ", "dim"),
            ("Dil Seçin", "bold bright_white"),
        )
    )
    console.print()

    result = questionary.select(
        message="",
        choices=choices,
        qmark="  ▸",
        style=Q_STYLE,
    ).ask()

    if result is None:
        import sys
        sys.exit(0)
    return result
