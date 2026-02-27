"""Step 3: Write the .env file."""

import os

from ..ui import step_header, step, ok
from .configure import Config
from ..i18n import t
from . import TOTAL_STEPS


def _frappe_version(erpnext_version: str) -> str:
    """Derive FRAPPE_VERSION from ERPNext version string.

    'v16.7.3' -> 'version-16'
    'v15.2.0' -> 'version-15'
    Falls back to 'version-16' if parsing fails.
    """
    try:
        major = erpnext_version.lstrip("v").split(".")[0]
        int(major)
        return f"version-{major}"
    except (IndexError, ValueError):
        return "version-16"


def _env_quote(value: str) -> str:
    """Quote a value for safe .env file inclusion.

    Wraps in single quotes if the value contains special characters.
    """
    special = set("#$\"'`\\!&|;() \t\n")
    if any(c in special for c in value):
        escaped = value.replace("'", "'\\''")
        return f"'{escaped}'"
    return value


def run_env_file(cfg: Config):
    """Generate the .env file from configuration."""
    step_header(3, TOTAL_STEPS, t("steps.env_file.title"))

    frappe_ver = _frappe_version(cfg.erpnext_version)

    step(t("steps.env_file.writing"))
    env_content = (
        f"ERPNEXT_VERSION={cfg.erpnext_version}\n"
        f"FRAPPE_VERSION={frappe_ver}\n"
        f"DB_PASSWORD={_env_quote(cfg.db_password)}\n"
        f"FRAPPE_SITE_NAME_HEADER={cfg.site_name}\n"
        f"HTTP_PUBLISH_PORT={cfg.http_port}\n"
        f"LETSENCRYPT_EMAIL=mail@example.com\n"
    )

    # Atomic write: write to temp file, then rename
    fd = os.open(".env.tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(fd, "w") as f:
            f.write(env_content)
        os.replace(".env.tmp", ".env")
    except Exception:
        try:
            os.unlink(".env.tmp")
        except OSError:
            pass
        raise

    ok(t("steps.env_file.done"))
