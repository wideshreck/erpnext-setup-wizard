"""Fetch ERPNext release versions from the GitHub API."""

import json
import re
import urllib.request
import urllib.error

_TAGS_URL = "https://api.github.com/repos/frappe/erpnext/tags"
_PER_PAGE = 100
_TIMEOUT = 10
_MIN_MAJOR = 14
_STABLE_RE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def fetch_erpnext_versions() -> list[str]:
    """Fetch stable ERPNext versions (v14+) from GitHub Tags API.

    Returns a list of version strings sorted newest-first.
    Returns an empty list on any network/API failure.
    """
    tags: list[str] = []
    page = 1

    try:
        while True:
            url = f"{_TAGS_URL}?per_page={_PER_PAGE}&page={page}"
            req = urllib.request.Request(
                url, headers={"Accept": "application/vnd.github.v3+json"}
            )
            with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                data = json.loads(resp.read().decode())

            if not data:
                break

            for tag in data:
                name = tag["name"]
                m = _STABLE_RE.match(name)
                if m and int(m.group(1)) >= _MIN_MAJOR:
                    tags.append(name)

            if len(data) < _PER_PAGE:
                break
            page += 1

    except (urllib.error.URLError, OSError, json.JSONDecodeError, KeyError, TypeError):
        return []

    def _sort_key(v: str) -> tuple[int, ...]:
        m = _STABLE_RE.match(v)
        return (int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else (0, 0, 0)

    # Sort by semver descending (newest first)
    tags.sort(key=_sort_key, reverse=True)
    return tags
