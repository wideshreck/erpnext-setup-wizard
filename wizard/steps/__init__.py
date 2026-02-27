"""Wizard steps."""

TOTAL_STEPS = 5

from .prerequisites import run_prerequisites
from .configure import run_configure
from .env_file import run_env_file
from .docker import run_docker
from .site import run_site

__all__ = [
    "TOTAL_STEPS",
    "run_prerequisites",
    "run_configure",
    "run_env_file",
    "run_docker",
    "run_site",
]
