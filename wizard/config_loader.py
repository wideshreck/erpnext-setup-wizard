"""Load configuration from CLI arguments or YAML file for unattended mode."""

import argparse
import re
import sys

import yaml

from .steps.configure import Config


# ── Shared argument helpers ─────────────────────────────────────

def _add_lang_arg(parser: argparse.ArgumentParser) -> None:
    """Add --lang to a subparser so it works in any position.

    Uses SUPPRESS default so the subparser does not override a value
    already set by the root parser when --lang appears before the subcommand.
    """
    parser.add_argument("--lang", type=str, default=argparse.SUPPRESS,
                        help="Language code (e.g., tr, en)")


def _add_ssh_args(parser: argparse.ArgumentParser) -> None:
    """Add SSH-related arguments to *parser*."""
    ssh = parser.add_argument_group("SSH options")
    ssh.add_argument("--ssh-host", type=str)
    ssh.add_argument("--ssh-user", type=str)
    ssh.add_argument("--ssh-port", type=int)
    ssh.add_argument("--ssh-key", type=str)


def _add_project_arg(parser: argparse.ArgumentParser, default: str = "frappe_docker") -> None:
    """Add --project flag to *parser*."""
    parser.add_argument(
        "--project", type=str, default=default,
        help="Docker Compose project directory (default: %(default)s)",
    )


# ── Parser builder ──────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with subcommands.

    Global flag:  --lang
    Subcommands:  setup (default), upgrade, exec, status
    """
    parser = argparse.ArgumentParser(
        description="ERPNext Setup Wizard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--lang", type=str, help="Language code (e.g., tr, en)")

    # ── Subcommands ─────────────────────────────────────────
    subparsers = parser.add_subparsers(dest="command")

    # ── setup ────────────────────────────────────────────────
    setup_p = subparsers.add_parser(
        "setup", help="Run the interactive setup wizard (default)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    _add_lang_arg(setup_p)
    setup_p.add_argument("--config", type=str,
                         help="Path to YAML config file for unattended mode")

    # Deploy mode
    setup_p.add_argument("--mode", choices=["local", "production", "remote"],
                         help="Deployment mode")
    setup_p.add_argument("--site-name", type=str)
    setup_p.add_argument("--version", type=str,
                         help="ERPNext version (e.g., v16.7.3)")
    setup_p.add_argument("--db-type", choices=["mariadb", "postgres"],
                         default=None)
    setup_p.add_argument("--http-port", type=str)
    setup_p.add_argument("--db-password", type=str)
    setup_p.add_argument("--admin-password", type=str)
    setup_p.add_argument("--domain", type=str)
    setup_p.add_argument("--letsencrypt-email", type=str)
    setup_p.add_argument("--apps", type=str,
                         help="Comma-separated app names")

    # New setup flags (future features)
    setup_p.add_argument("--custom-apps", type=str,
                         help="Comma-separated url:branch pairs for private apps")
    setup_p.add_argument("--backup-cron", type=str,
                         help='Backup schedule (e.g. "@every 6h")')
    setup_p.add_argument("--sites", type=str,
                         help="Comma-separated extra site names")
    setup_p.add_argument("--enable-portainer", action="store_true",
                         help="Enable Portainer container management UI")
    setup_p.add_argument("--build-image", action="store_true",
                         help="Build a custom Docker image")
    setup_p.add_argument("--image-tag", type=str,
                         default="custom-erpnext:latest",
                         help="Tag for the custom image (default: %(default)s)")
    setup_p.add_argument("--enable-autoheal", action="store_true",
                         help="Enable Docker autoheal for container restarts")

    _add_ssh_args(setup_p)

    # SMTP
    smtp = setup_p.add_argument_group("SMTP options")
    smtp.add_argument("--smtp-host", type=str)
    smtp.add_argument("--smtp-port", type=int)
    smtp.add_argument("--smtp-user", type=str)
    smtp.add_argument("--smtp-password", type=str)
    smtp.add_argument("--smtp-no-tls", action="store_true")

    # Backup
    backup = setup_p.add_argument_group("Backup options")
    backup.add_argument("--backup-s3-endpoint", type=str)
    backup.add_argument("--backup-s3-bucket", type=str)
    backup.add_argument("--backup-s3-access-key", type=str)
    backup.add_argument("--backup-s3-secret-key", type=str)

    # ── upgrade ──────────────────────────────────────────────
    upgrade_p = subparsers.add_parser(
        "upgrade", help="Upgrade an existing ERPNext installation",
    )
    _add_lang_arg(upgrade_p)
    upgrade_p.add_argument("--version", type=str,
                           help="Target ERPNext version (e.g., v16.8.0)")
    _add_project_arg(upgrade_p)
    _add_ssh_args(upgrade_p)

    # ── exec ─────────────────────────────────────────────────
    exec_p = subparsers.add_parser(
        "exec", help="Execute a command in a running container",
    )
    _add_lang_arg(exec_p)
    _add_project_arg(exec_p)
    exec_p.add_argument("--service", type=str, default="backend",
                        help="Service name (default: %(default)s)")
    _add_ssh_args(exec_p)
    exec_p.add_argument("cmd", nargs=argparse.REMAINDER,
                        help="Command to run in the container")

    # ── status ───────────────────────────────────────────────
    status_p = subparsers.add_parser(
        "status", help="Show status of the ERPNext stack",
    )
    _add_lang_arg(status_p)
    _add_project_arg(status_p)
    _add_ssh_args(status_p)

    return parser


# ── Config loading helpers ──────────────────────────────────────

def _require(data: dict, key: str, context: str = "config file") -> str:
    """Return data[key] or exit with a clear error if missing."""
    if key not in data:
        print(f"Error: Required field '{key}' missing from {context}.", file=sys.stderr)
        sys.exit(1)
    return data[key]


def _validate_config(cfg: Config) -> None:
    """Validate a Config object, raising SystemExit on invalid values."""
    errors = []

    # Required fields
    if not cfg.site_name:
        errors.append("site_name is required")
    if not cfg.erpnext_version:
        errors.append("erpnext_version is required")
    if not cfg.db_password:
        errors.append("db_password is required")
    if not cfg.admin_password:
        errors.append("admin_password is required")

    # Format validation
    if cfg.site_name and not re.fullmatch(r"[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)+", cfg.site_name):
        errors.append(f"Invalid site_name: {cfg.site_name}")
    if cfg.erpnext_version and not re.fullmatch(r"v\d+\.\d+\.\d+", cfg.erpnext_version):
        errors.append(f"Invalid erpnext_version: {cfg.erpnext_version}")
    if cfg.deploy_mode == "local" and cfg.http_port:
        if not (cfg.http_port.isdigit() and 1024 <= int(cfg.http_port) <= 65535):
            errors.append(f"Invalid http_port: {cfg.http_port}")

    # Mode-specific required fields
    if cfg.deploy_mode in ("production", "remote"):
        if not cfg.domain:
            errors.append("domain is required for production/remote mode")
        if not cfg.letsencrypt_email:
            errors.append("letsencrypt_email is required for production/remote mode")
        elif not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", cfg.letsencrypt_email):
            errors.append(f"Invalid letsencrypt_email format: {cfg.letsencrypt_email}")
    if cfg.deploy_mode == "remote":
        if not cfg.ssh_host:
            errors.append("ssh_host is required for remote mode")

    if errors:
        print("Configuration errors:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)


def _config_from_yaml(path: str) -> Config:
    """Parse a YAML config file into a Config object."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Config file not found: {path}", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error: Invalid YAML in {path}: {e}", file=sys.stderr)
        sys.exit(1)

    if not isinstance(data, dict):
        print(f"Error: Config file must contain a YAML mapping, got {type(data).__name__}.", file=sys.stderr)
        sys.exit(1)

    smtp = data.get("smtp", {})
    backup = data.get("backup", {})
    ssh = data.get("ssh", {})

    for section_name, section_val in [("smtp", smtp), ("backup", backup), ("ssh", ssh)]:
        if section_val and not isinstance(section_val, dict):
            print(f"Error: '{section_name}' section must be a mapping, got {type(section_val).__name__}.", file=sys.stderr)
            sys.exit(1)

    # Parse custom_apps list from YAML
    raw_custom_apps = data.get("custom_apps", [])
    custom_apps = []
    if isinstance(raw_custom_apps, list):
        for entry in raw_custom_apps:
            if isinstance(entry, dict) and "url" in entry:
                url = entry["url"]
                branch = entry.get("branch", "main")
                name = url.rstrip("/").rstrip(".git").split("/")[-1]
                custom_apps.append({"url": url, "branch": branch, "name": name})

    cfg = Config(
        deploy_mode=data.get("mode", "local"),
        site_name=_require(data, "site_name"),
        erpnext_version=_require(data, "erpnext_version"),
        db_type=data.get("db_type", "mariadb"),
        http_port=str(data.get("http_port", "8080")),
        db_password=_require(data, "db_password"),
        admin_password=_require(data, "admin_password"),
        extra_apps=data.get("extra_apps", []),
        community_apps=[],
        custom_apps=custom_apps,
        domain=data.get("domain", ""),
        letsencrypt_email=data.get("letsencrypt_email", ""),
        ssh_host=ssh.get("host", ""),
        ssh_user=ssh.get("user", "root"),
        ssh_port=ssh.get("port", 22),
        ssh_key_path=ssh.get("key_path", ""),
        smtp_host=smtp.get("host", ""),
        smtp_port=smtp.get("port", 587),
        smtp_user=smtp.get("user", ""),
        smtp_password=smtp.get("password", ""),
        smtp_use_tls=smtp.get("use_tls", True),
        backup_enabled=bool(backup),
        backup_s3_endpoint=backup.get("s3_endpoint", ""),
        backup_s3_bucket=backup.get("s3_bucket", ""),
        backup_s3_access_key=backup.get("s3_access_key", ""),
        backup_s3_secret_key=backup.get("s3_secret_key", ""),
        backup_cron=data.get("backup_cron", ""),
    )
    _validate_config(cfg)
    return cfg


def _config_from_args(args) -> Config | None:
    """Try to build Config from CLI args. Returns None if not enough args for unattended."""
    required = [
        getattr(args, "mode", None),
        getattr(args, "site_name", None),
        getattr(args, "version", None),
        getattr(args, "db_password", None),
        getattr(args, "admin_password", None),
    ]
    if not all(required):
        return None

    # Parse --custom-apps "url1:branch1,url2:branch2"
    custom_apps = []
    raw_custom_apps = getattr(args, "custom_apps", None)
    if raw_custom_apps:
        for pair in raw_custom_apps.split(","):
            pair = pair.strip()
            if not pair:
                continue
            if ":" in pair:
                # Split on last colon to handle URLs with colons (e.g. https://...)
                # Format: url:branch — find the branch after the last colon
                # But URLs contain "://" so we need to be smarter.
                # Strategy: if it looks like it ends with :branchname (no slashes),
                # split there; otherwise treat the whole thing as URL with default branch.
                last_colon = pair.rfind(":")
                potential_branch = pair[last_colon + 1:]
                if "/" not in potential_branch and potential_branch:
                    url = pair[:last_colon]
                    branch = potential_branch
                else:
                    url = pair
                    branch = "main"
            else:
                url = pair
                branch = "main"
            name = url.rstrip("/").rstrip(".git").split("/")[-1]
            custom_apps.append({"url": url, "branch": branch, "name": name})

    cfg = Config(
        deploy_mode=args.mode,
        site_name=args.site_name,
        erpnext_version=args.version,
        db_type=getattr(args, "db_type", None) or "mariadb",
        http_port=getattr(args, "http_port", None) or "8080",
        db_password=args.db_password,
        admin_password=args.admin_password,
        extra_apps=args.apps.split(",") if getattr(args, "apps", None) else [],
        community_apps=[],
        custom_apps=custom_apps,
        domain=getattr(args, "domain", None) or "",
        letsencrypt_email=getattr(args, "letsencrypt_email", None) or "",
        ssh_host=getattr(args, "ssh_host", None) or "",
        ssh_user=getattr(args, "ssh_user", None) or "root",
        ssh_port=getattr(args, "ssh_port", None) or 22,
        ssh_key_path=getattr(args, "ssh_key", None) or "",
        smtp_host=getattr(args, "smtp_host", None) or "",
        smtp_port=getattr(args, "smtp_port", None) or 587,
        smtp_user=getattr(args, "smtp_user", None) or "",
        smtp_password=getattr(args, "smtp_password", None) or "",
        smtp_use_tls=not getattr(args, "smtp_no_tls", False),
        backup_enabled=bool(getattr(args, "backup_s3_bucket", None)),
        backup_s3_endpoint=getattr(args, "backup_s3_endpoint", None) or "",
        backup_s3_bucket=getattr(args, "backup_s3_bucket", None) or "",
        backup_s3_access_key=getattr(args, "backup_s3_access_key", None) or "",
        backup_s3_secret_key=getattr(args, "backup_s3_secret_key", None) or "",
        backup_cron=getattr(args, "backup_cron", None) or "",
    )
    _validate_config(cfg)
    return cfg


def load_config(args) -> Config | None:
    """Try to load config from YAML file or CLI args.

    Returns Config for unattended mode, or None to fall through to interactive.
    """
    config_path = getattr(args, "config", None)
    if config_path:
        return _config_from_yaml(config_path)
    return _config_from_args(args)
