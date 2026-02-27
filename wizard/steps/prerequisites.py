"""Step 1: Check Docker, Docker Compose, Git, and frappe_docker repo."""

import os
import sys

from ..ui import step_header, step, ok, fail, info
from ..utils import check_tool, run
from ..ssh import SSHExecutor
from ..i18n import t
from . import TOTAL_STEPS
from .configure import Config


def _check_remote_tool(executor: SSHExecutor, name: str, cmd: str) -> bool:
    """Check a tool exists on the remote host."""
    step(t("steps.prerequisites.checking_remote", name=name))
    code, out, _ = executor.run(cmd, capture=True)
    if code != 0:
        fail(t("steps.prerequisites.remote_not_found", name=name))
        return False
    version = out.strip()
    ok(t("steps.prerequisites.remote_found", name=name, version=version))
    return True


def run_prerequisites(cfg: Config, executor):
    """Run prerequisite checks. Exits on failure."""
    step_header(1, TOTAL_STEPS, t("steps.prerequisites.title"))

    if cfg.deploy_mode == "remote":
        # Check local SSH tools
        ssh_ver = check_tool("SSH", "ssh -V 2>&1")
        if not ssh_ver:
            info(t("steps.prerequisites.install_ssh"))
            sys.exit(1)

        # Test SSH connection
        step(t("steps.prerequisites.testing_ssh"))
        if not executor.test_connection():
            fail(t("steps.prerequisites.ssh_failed"))
            sys.exit(1)
        ok(t("steps.prerequisites.ssh_ok"))

        from ..theme import console
        console.print()

        # Check remote tools
        if not _check_remote_tool(executor, "Docker", "docker --version"):
            sys.exit(1)
        if not _check_remote_tool(executor, "Docker Compose", "docker compose version"):
            sys.exit(1)
        if not _check_remote_tool(executor, "Git", "git --version"):
            sys.exit(1)

        # Clone frappe_docker on remote if needed
        console.print()
        step(t("steps.prerequisites.checking_remote_folder"))
        code, _, _ = executor.run("test -f ~/frappe_docker/compose.yaml", capture=True)
        if code != 0:
            step(t("steps.prerequisites.cloning_repo_remote"))
            code = executor.run(
                "git clone https://github.com/frappe/frappe_docker ~/frappe_docker"
            )
            if code != 0:
                fail(t("steps.prerequisites.clone_failed"))
                sys.exit(1)
            ok(t("steps.prerequisites.repo_downloaded"))
        else:
            ok(t("steps.prerequisites.remote_folder_exists"))

    else:
        # Local / Production: existing logic
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
