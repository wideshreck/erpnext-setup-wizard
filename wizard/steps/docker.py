"""Step 4: Start Docker Compose containers."""

import sys

from ..theme import console
from ..ui import step_header, step, ok, fail, info, animated_wait
from ..utils import run
from ..i18n import t
from . import TOTAL_STEPS

COMPOSE_CMD = (
    "docker compose -f compose.yaml "
    "-f overrides/compose.mariadb.yaml "
    "-f overrides/compose.redis.yaml "
    "-f overrides/compose.noproxy.yaml"
)


def run_docker():
    """Bring up Docker Compose stack."""
    step_header(4, TOTAL_STEPS, t("steps.docker.title"))

    step(t("steps.docker.cleaning"))
    run(f"{COMPOSE_CMD} down -v")
    ok(t("steps.docker.cleaned"))

    console.print()
    step(t("steps.docker.starting"))
    info(t("steps.docker.first_time_hint"))
    code = run(f"{COMPOSE_CMD} up -d")
    if code != 0:
        fail(t("steps.docker.start_failed"))
        sys.exit(1)
    ok(t("steps.docker.running"))

    console.print()
    animated_wait(25, t("steps.docker.waiting_db"))
