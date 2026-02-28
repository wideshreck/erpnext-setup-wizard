"""Step 3: Write the .env file."""

import os

from ..ui import step_header, step, ok, info
from ..utils import version_branch
from .configure import Config
from ..i18n import t
from . import TOTAL_STEPS


def _env_quote(value: str) -> str:
    """Quote a value for safe Docker Compose .env file inclusion.

    Docker Compose only supports double-quoted values in .env files.
    """
    needs_quoting = set("#$\"'`\\!&|;() \t\n\r")
    if any(c in needs_quoting for c in value):
        escaped = (value
                   .replace("\\", "\\\\")
                   .replace('"', '\\"')
                   .replace("$", "\\$")
                   .replace("`", "\\`")
                   .replace("\n", "\\n")
                   .replace("\r", "\\r"))
        return f'"{escaped}"'
    return value


def _build_env_content(cfg: Config) -> str:
    """Build .env file content based on deploy mode."""
    frappe_ver = version_branch(cfg.erpnext_version)

    lines = [
        f"ERPNEXT_VERSION={cfg.erpnext_version}",
        f"FRAPPE_VERSION={frappe_ver}",
        f"DB_PASSWORD={_env_quote(cfg.db_password)}",
        f"FRAPPE_SITE_NAME_HEADER={cfg.site_name}",
    ]

    if cfg.deploy_mode == "local":
        lines.append(f"HTTP_PUBLISH_PORT={cfg.http_port}")
        lines.append("LETSENCRYPT_EMAIL=mail@example.com")
    else:
        lines.append(f"LETSENCRYPT_EMAIL={_env_quote(cfg.letsencrypt_email)}")
        lines.append(f"SITES_RULE=Host(`{cfg.domain}`)")

    return "\n".join(lines) + "\n"


def run_env_file(cfg: Config, executor):
    """Generate the .env file from configuration."""
    step_header(3, TOTAL_STEPS, t("steps.env_file.title"))

    step(t("steps.env_file.writing"))
    env_content = _build_env_content(cfg)

    if cfg.deploy_mode == "remote":
        tmp_path = ".env.remote.tmp"
        try:
            with open(tmp_path, "w") as f:
                f.write(env_content)
            executor.upload(tmp_path, "~/frappe_docker/.env")
            info(t("steps.env_file.uploaded"))
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
    else:
        tmp_path = ".env.tmp"
        try:
            os.unlink(tmp_path)
        except FileNotFoundError:
            pass
        fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(fd, "w") as f:
                f.write(env_content)
            os.replace(tmp_path, ".env")
        except Exception:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    ok(t("steps.env_file.done"))
