"""Open an interactive shell in a running ERPNext container."""

import os
import shlex
import sys


def run_exec(args):
    """Open interactive shell in the specified container service."""
    service = getattr(args, "service", "backend")
    project = getattr(args, "project", "frappe_docker")

    # Get any extra command passed after --
    extra_cmd = getattr(args, "cmd", [])
    # Filter out the leading '--' if present
    if extra_cmd and extra_cmd[0] == "--":
        extra_cmd = extra_cmd[1:]

    # Default to bash if no command specified
    container_cmd = extra_cmd if extra_cmd else ["bash"]

    if getattr(args, "ssh_host", None):
        # Remote: SSH into server, then docker exec
        ssh_parts = ["ssh", "-t"]
        if getattr(args, "ssh_key", None):
            ssh_parts.extend(["-i", args.ssh_key])
        if getattr(args, "ssh_port", None):
            ssh_parts.extend(["-p", str(args.ssh_port)])
        user = getattr(args, "ssh_user", None) or "root"
        ssh_parts.append(f"{user}@{args.ssh_host}")
        safe_project = shlex.quote(project)
        safe_service = shlex.quote(service)
        safe_cmd = " ".join(shlex.quote(c) for c in container_cmd)
        ssh_parts.append(
            f"cd ~/{safe_project} && docker compose exec {safe_service} {safe_cmd}"
        )
        os.execvp("ssh", ssh_parts)
    else:
        # Local: direct docker compose exec
        try:
            os.chdir(project)
        except FileNotFoundError:
            print(f"Error: Directory '{project}' not found.", file=sys.stderr)
            sys.exit(1)
        os.execvp("docker", [
            "docker", "compose", "exec", service, *container_cmd
        ])
