"""Shell utilities: run commands, check tools, clear screen."""

import os
import platform
import subprocess

from .ui import step, ok, fail
from .i18n import t


def clear_screen():
    os.system("cls" if platform.system() == "Windows" else "clear")


def run(cmd: str, capture: bool = False):
    """Run a shell command. Returns (code, stdout, stderr) if capture=True, else code."""
    if capture:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return result.returncode, result.stdout, result.stderr
    else:
        result = subprocess.run(cmd, shell=True)
        return result.returncode


def check_tool(name: str, cmd: str) -> str:
    """Check a CLI tool exists and return its version string, or '' on failure."""
    step(t("utils.checking", name=name))
    code, out, err = run(cmd, capture=True)
    if code != 0:
        fail(t("utils.not_found", name=name))
        return ""
    version = out.strip()
    ok(t("utils.found", name=name, version=version))
    return version
