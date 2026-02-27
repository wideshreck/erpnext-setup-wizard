"""Registry of optional Frappe apps available for installation."""

from typing import NamedTuple


class AppInfo(NamedTuple):
    """Metadata for an installable Frappe app.

    Attributes:
        repo_name: GitHub repo name under github.com/frappe/
        display_name: Human-readable name for UI
        i18n_key: Dot-notation key for t() description lookup
        branch: Override branch name, or None to use version-{major}
    """
    repo_name: str
    display_name: str
    i18n_key: str
    branch: str | None = None


OPTIONAL_APPS: list[AppInfo] = [
    AppInfo("hrms",           "HRMS",           "apps.hrms"),
    AppInfo("payments",       "Payments",       "apps.payments"),
    AppInfo("healthcare",     "Healthcare",     "apps.healthcare"),
    AppInfo("education",      "Education",      "apps.education"),
    AppInfo("lending",        "Lending",        "apps.lending"),
    AppInfo("webshop",        "Webshop",        "apps.webshop"),
    AppInfo("print_designer", "Print Designer", "apps.print_designer"),
    AppInfo("wiki",           "Wiki",           "apps.wiki"),
]
