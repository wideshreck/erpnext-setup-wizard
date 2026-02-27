"""Executor pattern for local and SSH command execution.

Provides LocalExecutor and SSHExecutor with the same interface so that
step functions can run commands identically on the local machine or a
remote server.
"""

import subprocess


class LocalExecutor:
    """Execute commands on the local machine via subprocess."""

    def run(self, cmd: str, capture: bool = False) -> int | tuple[int, str, str]:
        """Run a shell command locally.

        Returns (returncode, stdout, stderr) if capture=True, else returncode.
        """
        if capture:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
            return result.returncode, result.stdout, result.stderr
        else:
            result = subprocess.run(cmd, shell=True)
            return result.returncode

    def upload(self, local_path: str, remote_path: str):
        """Copy a file locally (local-to-local)."""
        import shutil

        shutil.copy2(local_path, remote_path)


class SSHExecutor:
    """Execute commands on a remote server via SSH."""

    def __init__(self, host: str, user: str, port: int = 22, key_path: str = ""):
        self.host = host
        self.user = user
        self.port = port
        self.key_path = key_path

    def _ssh_base(self) -> list[str]:
        """Build the base ssh command with connection options."""
        parts = ["ssh", "-o", "StrictHostKeyChecking=accept-new", "-p", str(self.port)]
        if self.key_path:
            parts.extend(["-i", self.key_path])
        parts.append(f"{self.user}@{self.host}")
        return parts

    def _scp_base(self) -> list[str]:
        """Build the base scp command with connection options."""
        parts = ["scp", "-o", "StrictHostKeyChecking=accept-new", "-P", str(self.port)]
        if self.key_path:
            parts.extend(["-i", self.key_path])
        return parts

    def run(self, cmd: str, capture: bool = False) -> int | tuple[int, str, str]:
        """Run a command on the remote server via SSH.

        Returns (returncode, stdout, stderr) if capture=True, else returncode.
        """
        full_cmd = self._ssh_base() + [cmd]
        if capture:
            result = subprocess.run(full_cmd, capture_output=True, text=True)
            return result.returncode, result.stdout, result.stderr
        else:
            result = subprocess.run(full_cmd)
            return result.returncode

    def upload(self, local_path: str, remote_path: str):
        """Upload a file to the remote server via SCP."""
        dest = f"{self.user}@{self.host}:{remote_path}"
        full_cmd = self._scp_base() + [local_path, dest]
        result = subprocess.run(full_cmd)
        if result.returncode != 0:
            raise RuntimeError(f"SCP upload failed: {local_path} -> {dest}")

    def test_connection(self) -> bool:
        """Test whether the SSH connection works."""
        code, _, _ = self.run("echo ok", capture=True)
        return code == 0


def create_executor(cfg) -> LocalExecutor | SSHExecutor:
    """Create the appropriate executor based on deploy_mode in the config.

    Args:
        cfg: A Config dataclass with deploy_mode, ssh_host, ssh_user,
             ssh_port, and ssh_key_path fields.
    """
    if cfg.deploy_mode == "remote":
        return SSHExecutor(
            host=cfg.ssh_host,
            user=cfg.ssh_user,
            port=cfg.ssh_port,
            key_path=cfg.ssh_key_path,
        )
    return LocalExecutor()
