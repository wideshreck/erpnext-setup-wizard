"""Step 1: Check Docker, Docker Compose, Git, and frappe_docker repo."""

import os
import sys

from ..ui import step_header, step, ok, fail, info
from ..utils import check_tool, run
from ..i18n import t
from . import TOTAL_STEPS


def run_prerequisites():
    """Run prerequisite checks. Exits on failure."""
    step_header(1, TOTAL_STEPS, t("steps.prerequisites.title"))

    docker_ver = check_tool("Docker", "docker --version")
    if not docker_ver:
        info(t("steps.prerequisites.install_docker"))
        sys.exit(1)

    compose_ver = check_tool("Docker Compose", "docker compose version")
    if not compose_ver:
        sys.exit(1)

    from ..theme import console
    console.print()
    step(t("steps.prerequisites.checking_folder"))

    if not os.path.exists("compose.yaml"):
        info(t("steps.prerequisites.compose_not_found"))

        git_ver = check_tool("Git", "git --version")
        if not git_ver:
            info(t("steps.prerequisites.install_git"))
            sys.exit(1)

        if not os.path.exists("frappe_docker"):
            step(t("steps.prerequisites.cloning_repo"))
            code = run("git clone https://github.com/frappe/frappe_docker")
            if code != 0:
                fail(t("steps.prerequisites.clone_failed"))
                sys.exit(1)
            ok(t("steps.prerequisites.repo_downloaded"))
        else:
            ok(t("steps.prerequisites.folder_exists"))

        os.chdir("frappe_docker")
        info(t("steps.prerequisites.working_dir", cwd=os.getcwd()))

    ok(t("steps.prerequisites.correct_dir"))
