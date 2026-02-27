"""Step 3: Write the .env file."""

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
        int(major)  # validate it is a number
        return f"version-{major}"
    except (IndexError, ValueError):
        return "version-16"


def run_env_file(cfg: Config):
    """Generate the .env file from configuration."""
    step_header(3, TOTAL_STEPS, t("steps.env_file.title"))

    frappe_ver = _frappe_version(cfg.erpnext_version)

    step(t("steps.env_file.writing"))
    env_content = (
        f"ERPNEXT_VERSION={cfg.erpnext_version}\n"
        f"FRAPPE_VERSION={frappe_ver}\n"
        f"DB_PASSWORD={cfg.db_password}\n"
        f"FRAPPE_SITE_NAME_HEADER={cfg.site_name}\n"
        f"HTTP_PUBLISH_PORT={cfg.http_port}\n"
        f"LETSENCRYPT_EMAIL=mail@example.com\n"
    )
    with open(".env", "w") as f:
        f.write(env_content)
    ok(t("steps.env_file.done"))
