"""Registry of optional Frappe apps available for installation."""

import shlex
from typing import NamedTuple

from .utils import run, version_branch


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


def detect_best_branch(repo_url: str, erpnext_version: str) -> str | None:
    """Detect best compatible branch via git ls-remote.

    Checks branches in priority order: version-{major} > main > master > develop.
    Returns the first match, or None if no suitable branch found.
    """
    target = version_branch(erpnext_version)
    code, stdout, _ = run(
        f"git ls-remote --heads {shlex.quote(repo_url)}", capture=True
    )
    if code != 0:
        return None

    branches = set()
    for line in stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) == 2:
            branches.add(parts[1].removeprefix("refs/heads/"))

    for candidate in [target, "main", "master", "develop"]:
        if candidate in branches:
            return candidate

    return None
