"""Step 4: Start Docker Compose containers."""

import sys

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

    return "docker compose " + " ".join(f"-f {f}" for f in files)


def run_docker(cfg: Config, executor):
    """Bring up Docker Compose stack."""
    step_header(4, TOTAL_STEPS, t("steps.docker.title"))

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
    wait_time = 35 if cfg.deploy_mode == "remote" else 25
    animated_wait(wait_time, t("steps.docker.waiting_db"))
