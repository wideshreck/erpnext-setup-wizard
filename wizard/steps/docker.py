"""Step 4: Start Docker Compose containers."""

import json
import sys
import time

from ..theme import console
from ..ui import step_header, step, ok, fail, info, animated_wait
from ..i18n import t
from .configure import Config
from . import TOTAL_STEPS


def build_compose_cmd(cfg: Config) -> str:
    """Build the docker compose command with correct override files."""
    files = ["compose.yaml"]

    if cfg.db_type == "postgres":
        files.append("overrides/compose.postgres.yaml")
    else:
        files.append("overrides/compose.mariadb.yaml")

    files.append("overrides/compose.redis.yaml")

    if cfg.deploy_mode == "local":
        files.append("overrides/compose.noproxy.yaml")
    else:
        files.append("overrides/compose.https.yaml")

    if cfg.backup_cron:
        files.append("overrides/compose.backup-cron.yaml")

    if cfg.enable_portainer:
        files.append("compose.portainer.yaml")

    cmd = "docker compose " + " ".join(f"-f {f}" for f in files)
    if cfg.deploy_mode == "remote":
        cmd = f"cd ~/frappe_docker && {cmd}"
    return cmd


def _write_portainer_overlay(executor, cfg):
    """Write compose.portainer.yaml overlay file."""
    content = '''services:
  portainer:
    image: portainer/portainer-ce:latest
    restart: unless-stopped
    ports:
      - "9443:9443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - portainer_data:/data

volumes:
  portainer_data:
'''
    if cfg.deploy_mode == "remote":
        import tempfile, os
        tmp = tempfile.mktemp(suffix=".yaml")
        try:
            with open(tmp, "w") as f:
                f.write(content)
            executor.upload(tmp, "~/frappe_docker/compose.portainer.yaml")
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
    else:
        with open("compose.portainer.yaml", "w") as f:
            f.write(content)


def _wait_for_healthy(executor, compose_cmd: str, timeout: int = 120) -> bool:
    """Poll container health until all services are running or timeout."""
    step(t("steps.docker.health_checking"))
    start = time.time()
    while time.time() - start < timeout:
        result = executor.run(f"{compose_cmd} ps --format json", capture=True)
        if isinstance(result, tuple):
            code, stdout, _ = result
        else:
            break  # fallback
        if code == 0 and stdout.strip():
            lines = stdout.strip().split("\n")
            all_up = True
            for line in lines:
                try:
                    svc = json.loads(line)
                    state = svc.get("State", "")
                    if state != "running":
                        all_up = False
                        break
                except (json.JSONDecodeError, KeyError):
                    all_up = False
                    break
            if all_up and len(lines) > 0:
                ok(t("steps.docker.all_healthy"))
                return True
        time.sleep(5)
    fail(t("steps.docker.health_timeout"))
    return False


def run_docker(cfg: Config, executor):
    """Bring up Docker Compose stack."""
    step_header(4, TOTAL_STEPS, t("steps.docker.title"))

    # Build custom Docker image if requested
    if cfg.build_image:
        from ..commands.build import run_build_image
        console.print()
        if not run_build_image(cfg, executor):
            sys.exit(1)

    # Write overlay files for optional services
    if cfg.enable_portainer:
        _write_portainer_overlay(executor, cfg)

    compose_cmd = build_compose_cmd(cfg)

    step(t("steps.docker.cleaning"))
    code = executor.run(f"{compose_cmd} down")
    if code != 0:
        fail(t("steps.docker.down_failed"))
        sys.exit(1)
    ok(t("steps.docker.cleaned"))

    console.print()
    step(t("steps.docker.starting"))
    info(t("steps.docker.first_time_hint"))
    code = executor.run(f"{compose_cmd} up -d")
    if code != 0:
        fail(t("steps.docker.start_failed"))
        sys.exit(1)
    ok(t("steps.docker.running"))

    console.print()
    # Try health polling first, fall back to timed wait
    if not _wait_for_healthy(executor, compose_cmd):
        wait_time = 35 if cfg.deploy_mode == "remote" else 25
        animated_wait(wait_time, t("steps.docker.waiting_db"))
