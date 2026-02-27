"""Load configuration from CLI arguments or YAML file for unattended mode."""

import argparse

import yaml

from .steps.configure import Config


def build_parser() -> argparse.ArgumentParser:
    """Build the full argument parser."""
    parser = argparse.ArgumentParser(
        description="ERPNext Setup Wizard",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--lang", type=str, help="Language code (e.g., tr, en)")
    parser.add_argument("--config", type=str, help="Path to YAML config file for unattended mode")

    # Deploy mode
    parser.add_argument("--mode", choices=["local", "production", "remote"],
                        help="Deployment mode")
    parser.add_argument("--site-name", type=str)
    parser.add_argument("--version", type=str, help="ERPNext version (e.g., v16.7.3)")
    parser.add_argument("--db-type", choices=["mariadb", "postgres"], default=None)
    parser.add_argument("--http-port", type=str)
    parser.add_argument("--db-password", type=str)
    parser.add_argument("--admin-password", type=str)
    parser.add_argument("--domain", type=str)
    parser.add_argument("--letsencrypt-email", type=str)
    parser.add_argument("--apps", type=str, help="Comma-separated app names")

    # SSH
    parser.add_argument("--ssh-host", type=str)
    parser.add_argument("--ssh-user", type=str)
    parser.add_argument("--ssh-port", type=int)
    parser.add_argument("--ssh-key", type=str)

    # SMTP
    parser.add_argument("--smtp-host", type=str)
    parser.add_argument("--smtp-port", type=int)
    parser.add_argument("--smtp-user", type=str)
    parser.add_argument("--smtp-password", type=str)
    parser.add_argument("--smtp-no-tls", action="store_true")

    # Backup
    parser.add_argument("--backup-s3-endpoint", type=str)
    parser.add_argument("--backup-s3-bucket", type=str)
    parser.add_argument("--backup-s3-access-key", type=str)
    parser.add_argument("--backup-s3-secret-key", type=str)

    return parser


def _config_from_yaml(path: str) -> Config:
    """Parse a YAML config file into a Config object."""
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    smtp = data.get("smtp", {})
    backup = data.get("backup", {})
    ssh = data.get("ssh", {})

    return Config(
        deploy_mode=data.get("mode", "local"),
        site_name=data["site_name"],
        erpnext_version=data["erpnext_version"],
        db_type=data.get("db_type", "mariadb"),
        http_port=str(data.get("http_port", "8080")),
        db_password=data["db_password"],
        admin_password=data["admin_password"],
        extra_apps=data.get("extra_apps", []),
        community_apps=[],
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
    )


def _config_from_args(args) -> Config | None:
    """Try to build Config from CLI args. Returns None if not enough args for unattended."""
    required = [args.mode, args.site_name, args.version,
                args.db_password, args.admin_password]
    if not all(required):
        return None

    return Config(
        deploy_mode=args.mode,
        site_name=args.site_name,
        erpnext_version=args.version,
        db_type=args.db_type or "mariadb",
        http_port=args.http_port or "8080",
        db_password=args.db_password,
        admin_password=args.admin_password,
        extra_apps=args.apps.split(",") if args.apps else [],
        community_apps=[],
        domain=args.domain or "",
        letsencrypt_email=args.letsencrypt_email or "",
        ssh_host=args.ssh_host or "",
        ssh_user=args.ssh_user or "root",
        ssh_port=args.ssh_port or 22,
        ssh_key_path=args.ssh_key or "",
        smtp_host=args.smtp_host or "",
        smtp_port=args.smtp_port or 587,
        smtp_user=args.smtp_user or "",
        smtp_password=args.smtp_password or "",
        smtp_use_tls=not args.smtp_no_tls,
        backup_enabled=bool(args.backup_s3_bucket),
        backup_s3_endpoint=args.backup_s3_endpoint or "",
        backup_s3_bucket=args.backup_s3_bucket or "",
        backup_s3_access_key=args.backup_s3_access_key or "",
        backup_s3_secret_key=args.backup_s3_secret_key or "",
    )


def load_config(args) -> Config | None:
    """Try to load config from YAML file or CLI args.

    Returns Config for unattended mode, or None to fall through to interactive.
    """
    if args.config:
        return _config_from_yaml(args.config)
    return _config_from_args(args)
