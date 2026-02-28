"""Build a custom Docker image with selected apps baked in."""

import base64
import json
import shlex

from ..theme import console
from ..ui import step, ok, fail, info
from ..i18n import t


def generate_apps_json(cfg) -> str:
    """Generate apps.json content from selected apps."""
    apps = [
        {"url": "https://github.com/frappe/erpnext", "branch": cfg.erpnext_version}
    ]
    for app_name in cfg.extra_apps:
        major = cfg.erpnext_version.split(".")[0].lstrip("v")
        apps.append({
            "url": f"https://github.com/frappe/{app_name}",
            "branch": f"version-{major}",
        })
    for app in getattr(cfg, "custom_apps", []):
        apps.append({"url": app["url"], "branch": app["branch"]})
    return json.dumps(apps)


def run_build_image(cfg, executor):
    """Build custom Docker image with apps baked in."""
    step(t("commands.build.generating_apps_json"))
    apps_json = generate_apps_json(cfg)
    apps_b64 = base64.b64encode(apps_json.encode()).decode()
    app_count = len(json.loads(apps_json))
    ok(t("commands.build.apps_json_ready", count=app_count))

    console.print()
    step(t("commands.build.building_image"))
    tag = getattr(cfg, "image_tag", "custom-erpnext:latest")
    frappe_branch = "version-" + cfg.erpnext_version.split(".")[0].lstrip("v")

    build_cmd = (
        f"docker build "
        f"--build-arg=APPS_JSON_BASE64={shlex.quote(apps_b64)} "
        f"--build-arg=FRAPPE_BRANCH={shlex.quote(frappe_branch)} "
        f"-t {shlex.quote(tag)} "
        f"-f images/custom/Containerfile ."
    )

    code = executor.run(build_cmd)
    if code == 0:
        ok(t("commands.build.image_built", tag=tag))
        return True
    else:
        fail(t("commands.build.build_failed"))
        return False
