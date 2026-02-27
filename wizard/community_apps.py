"""Discover community Frappe apps from awesome-frappe."""

import os
import re
import shlex
import shutil
import tempfile
from typing import NamedTuple

from .apps import OPTIONAL_APPS, detect_best_branch
from .utils import run


class CommunityApp(NamedTuple):
    """A community Frappe app discovered from awesome-frappe."""
    display_name: str
    repo_name: str
    repo_url: str
    branch: str


_AWESOME_FRAPPE_URL = "https://github.com/gavindsouza/awesome-frappe.git"
_GITHUB_LINK_RE = re.compile(
    r"\[([^\]]+)\]\((https://github\.com/[^/]+/[^/)#?]+)\)"
)


def fetch_community_apps(erpnext_version: str) -> list[CommunityApp]:
    """Fetch compatible community apps from awesome-frappe.

    Clones awesome-frappe (shallow), parses README.md for GitHub links,
    checks each app's branch compatibility via git ls-remote.
    Returns only apps that have a compatible branch and are NOT already
    in the official OPTIONAL_APPS list.

    Returns an empty list on any failure (network, parse, etc).
    """
    official_repos = {app.repo_name for app in OPTIONAL_APPS}
    # Also exclude frappe and erpnext themselves
    official_repos.update({"frappe", "erpnext", "bench", "frappe_docker"})

    tmpdir = tempfile.mkdtemp(prefix="awesome-frappe-")
    try:
        code, _, _ = run(
            f"git clone --depth 1 --quiet {shlex.quote(_AWESOME_FRAPPE_URL)} "
            f"{shlex.quote(tmpdir)}",
            capture=True,
        )
        if code != 0:
            return []

        readme_path = os.path.join(tmpdir, "README.md")
        if not os.path.exists(readme_path):
            return []

        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        entries = _GITHUB_LINK_RE.findall(content)
        if not entries:
            return []

        apps: list[CommunityApp] = []
        seen: set[str] = set()

        for display_name, url in entries:
            url = url.rstrip("/")
            parts = url.split("/")
            repo_name = parts[-1]
            if repo_name.endswith(".git"):
                repo_name = repo_name[:-4]
            org_repo = f"{parts[-2]}/{repo_name}"

            # Skip duplicates, official apps, and non-app repos
            if org_repo in seen or repo_name in official_repos:
                continue
            seen.add(org_repo)

            # Check branch compatibility
            repo_url = url if url.endswith(".git") else url + ".git"
            branch = detect_best_branch(repo_url, erpnext_version)
            if branch:
                apps.append(CommunityApp(
                    display_name=display_name,
                    repo_name=repo_name,
                    repo_url=repo_url,
                    branch=branch,
                ))

        return apps
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
