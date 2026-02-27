# ERPNext Setup Wizard — Improvements Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix all bugs, add input validation, improve security and code quality in the existing 5-step wizard — no new files, no new features.

**Architecture:** Targeted in-place edits across existing files. Shared `TOTAL_STEPS` constant moves to `wizard/steps/__init__.py`. `FRAPPE_VERSION` is derived from ERPNext version. `shlex.quote()` wraps all shell-interpolated user values. `questionary` validators added to all text fields.

**Tech Stack:** Python 3.10+, Rich ≥13.9.0, questionary ≥2.1.0, stdlib `shlex`, `re`

---

## Task 1: Move TOTAL_STEPS to shared constant

**Files:**
- Modify: `wizard/steps/__init__.py`
- Modify: `wizard/steps/prerequisites.py`
- Modify: `wizard/steps/configure.py`
- Modify: `wizard/steps/env_file.py`
- Modify: `wizard/steps/docker.py`
- Modify: `wizard/steps/site.py`

**Step 1: Add TOTAL_STEPS to `wizard/steps/__init__.py`**

Replace the entire file content with:
```python
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
```

**Step 2: Remove TOTAL_STEPS from each step file, import it instead**

In each of the 5 step files (`prerequisites.py`, `configure.py`, `env_file.py`, `docker.py`, `site.py`):

Remove the line:
```python
TOTAL_STEPS = 5
```

Add this import at the top of each file (after the existing imports):
```python
from . import TOTAL_STEPS
```

**Step 3: Verify — run the wizard's import chain**

```bash
cd /c/Users/clawd/Desktop/erpnext-setup-wizard
python -c "from wizard.steps import run_prerequisites, TOTAL_STEPS; print('TOTAL_STEPS =', TOTAL_STEPS)"
```
Expected output: `TOTAL_STEPS = 5`

**Step 4: Commit**

```bash
git init  # if not already a git repo
git add wizard/steps/__init__.py wizard/steps/prerequisites.py wizard/steps/configure.py wizard/steps/env_file.py wizard/steps/docker.py wizard/steps/site.py
git commit -m "refactor: move TOTAL_STEPS to shared constant in steps/__init__.py"
```

---

## Task 2: Fix FRAPPE_VERSION (dynamic, derived from ERPNext version)

**Files:**
- Modify: `wizard/steps/env_file.py`

**Background:** The current code hardcodes `FRAPPE_VERSION=version-15` for all ERPNext versions. The correct mapping is: ERPNext `vNN.x.x` → Frappe `version-NN`. For example `v16.7.3` → `version-16`.

**Step 1: Update `run_env_file` in `wizard/steps/env_file.py`**

Current code (lines 14-24):
```python
def run_env_file(cfg: Config):
    """Generate the .env file from configuration."""
    step_header(3, TOTAL_STEPS, t("steps.env_file.title"))

    step(t("steps.env_file.writing"))
    env_content = (
        f"ERPNEXT_VERSION={cfg.erpnext_version}\n"
        f"FRAPPE_VERSION=version-15\n"
        f"DB_PASSWORD={cfg.db_password}\n"
        f"FRAPPE_SITE_NAME_HEADER={cfg.site_name}\n"
        f"HTTP_PUBLISH_PORT={cfg.http_port}\n"
        f"LETSENCRYPT_EMAIL=mail@example.com\n"
    )
    with open(".env", "w") as f:
        f.write(env_content)
    ok(t("steps.env_file.done"))
```

Replace with:
```python
def _frappe_version(erpnext_version: str) -> str:
    """Derive FRAPPE_VERSION from ERPNext version string.

    'v16.7.3' -> 'version-16'
    'v15.2.0' -> 'version-15'
    Falls back to 'version-16' if parsing fails.
    """
    try:
        major = erpnext_version.lstrip("v").split(".")[0]
        int(major)  # validate it is a number
        return f"version-{major}"
    except (IndexError, ValueError):
        return "version-16"


def run_env_file(cfg: Config):
    """Generate the .env file from configuration."""
    step_header(3, TOTAL_STEPS, t("steps.env_file.title"))

    frappe_ver = _frappe_version(cfg.erpnext_version)

    step(t("steps.env_file.writing"))
    env_content = (
        f"ERPNEXT_VERSION={cfg.erpnext_version}\n"
        f"FRAPPE_VERSION={frappe_ver}\n"
        f"DB_PASSWORD={cfg.db_password}\n"
        f"FRAPPE_SITE_NAME_HEADER={cfg.site_name}\n"
        f"HTTP_PUBLISH_PORT={cfg.http_port}\n"
        f"LETSENCRYPT_EMAIL=mail@example.com\n"
    )
    with open(".env", "w") as f:
        f.write(env_content)
    ok(t("steps.env_file.done"))
```

**Step 2: Verify the helper function**

```bash
python -c "
from wizard.steps.env_file import _frappe_version
assert _frappe_version('v16.7.3') == 'version-16'
assert _frappe_version('v15.2.0') == 'version-15'
assert _frappe_version('v14.0.0') == 'version-14'
assert _frappe_version('bad-input') == 'version-16'
print('All assertions passed')
"
```
Expected: `All assertions passed`

**Step 3: Commit**

```bash
git add wizard/steps/env_file.py
git commit -m "fix: derive FRAPPE_VERSION dynamically from ERPNext version"
```

---

## Task 3: Fix docker.py — remove destructive `-v` flag

**Files:**
- Modify: `wizard/steps/docker.py`
- Modify: `wizard/i18n/tr.json`
- Modify: `wizard/i18n/en.json`
- Modify: `wizard/i18n/de.json`
- Modify: `wizard/i18n/es.json`
- Modify: `wizard/i18n/fr.json`
- Modify: `wizard/i18n/it.json`

**Background:** `docker compose down -v` removes named volumes, deleting all database data. On a re-run, this silently destroys existing ERPNext data. Should be `down` only.

**Step 1: Update `run_docker` in `wizard/steps/docker.py`**

Change line:
```python
    run(f"{COMPOSE_CMD} down -v")
```
To:
```python
    run(f"{COMPOSE_CMD} down")
```

Also update the cleaning message key from `"steps.docker.cleaning"` to keep it but update the i18n value to clarify data is preserved.

**Step 2: Update i18n cleaning message in all 6 language files**

In `wizard/i18n/tr.json`, change:
```json
"cleaning": "Önceki kurulum temizleniyor (varsa)…",
```
To:
```json
"cleaning": "Önceki konteynerler durduruluyor (veriler korunur)…",
```

In `wizard/i18n/en.json`, change:
```json
"cleaning": "Cleaning previous setup (if any)…",
```
To:
```json
"cleaning": "Stopping previous containers (data preserved)…",
```

In `wizard/i18n/de.json`, change:
```json
"cleaning": "Vorherige Einrichtung wird bereinigt (falls vorhanden)…",
```
To:
```json
"cleaning": "Vorherige Container werden gestoppt (Daten bleiben erhalten)…",
```

In `wizard/i18n/es.json`, change:
```json
"cleaning": "Limpiando instalación anterior (si existe)…",
```
To:
```json
"cleaning": "Deteniendo contenedores anteriores (datos preservados)…",
```

In `wizard/i18n/fr.json`, change:
```json
"cleaning": "Nettoyage de l'installation précédente (si existante)…",
```
To:
```json
"cleaning": "Arrêt des conteneurs précédents (données préservées)…",
```

In `wizard/i18n/it.json`, change:
```json
"cleaning": "Pulizia dell'installazione precedente (se presente)…",
```
To:
```json
"cleaning": "Arresto dei container precedenti (dati preservati)…",
```

**Step 3: Verify**

```bash
python -c "
import json
for lang in ['tr', 'en', 'de', 'es', 'fr', 'it']:
    with open(f'wizard/i18n/{lang}.json') as f:
        data = json.load(f)
    msg = data['steps']['docker']['cleaning']
    print(f'{lang}: {msg}')
"
```
Expected: 6 lines, none containing `down -v` or `cleaning`.

**Step 4: Commit**

```bash
git add wizard/steps/docker.py wizard/i18n/tr.json wizard/i18n/en.json wizard/i18n/de.json wizard/i18n/es.json wizard/i18n/fr.json wizard/i18n/it.json
git commit -m "fix: remove destructive -v flag from docker down, preserve volumes"
```

---

## Task 4: Fix site.py — shell-safe interpolation with shlex.quote

**Files:**
- Modify: `wizard/steps/site.py`

**Background:** `cfg.site_name`, `cfg.db_password`, `cfg.admin_password` are interpolated directly into shell commands. A password like `my pass$word` or `it's"fine"` would break the command or allow shell injection. `shlex.quote()` wraps the value in single quotes and escapes any single quotes within it.

**Step 1: Add shlex import to `wizard/steps/site.py`**

At the top of the file, after the existing `import platform` and `import sys` lines, add:
```python
import shlex
```

**Step 2: Update `_create_site` to use shlex.quote**

Find the `code = run(...)` block in `_create_site` (around line 29):

Current code:
```python
    code = run(
        f"docker compose exec backend bench new-site {cfg.site_name} "
        f"--install-app erpnext "
        f"--db-root-password {cfg.db_password} "
        f"--admin-password {cfg.admin_password}"
    )
```

Replace with:
```python
    code = run(
        f"docker compose exec backend bench new-site {shlex.quote(cfg.site_name)} "
        f"--install-app erpnext "
        f"--db-root-password {shlex.quote(cfg.db_password)} "
        f"--admin-password {shlex.quote(cfg.admin_password)}"
    )
```

Also fix the scheduler command in `_create_site` (around line 42):

Current:
```python
    run(f"docker compose exec backend bench --site {cfg.site_name} enable-scheduler")
```

Replace with:
```python
    run(f"docker compose exec backend bench --site {shlex.quote(cfg.site_name)} enable-scheduler")
```

**Step 3: Verify shlex.quote behavior**

```bash
python -c "
import shlex
# Normal values pass through cleanly
assert shlex.quote('mysite.localhost') == \"'mysite.localhost'\" or shlex.quote('mysite.localhost') == 'mysite.localhost'
# Dangerous values are escaped
dangerous = \"it's fine\"
quoted = shlex.quote(dangerous)
print(f'dangerous: {repr(dangerous)} -> quoted: {repr(quoted)}')
# Confirm it starts/ends with quote and escapes content
assert '\$' not in quoted or quoted.startswith(\"'\")
print('shlex.quote working correctly')
"
```

**Step 4: Commit**

```bash
git add wizard/steps/site.py
git commit -m "fix: use shlex.quote to prevent shell injection in site creation commands"
```

---

## Task 5: Add validate parameter to ask_field in prompts.py

**Files:**
- Modify: `wizard/prompts.py`

**Background:** Currently `ask_field()` passes no validator to `questionary.text()`. We need an optional `validate` callable parameter so `configure.py` can add inline field validation.

**Step 1: Update `ask_field` signature and body in `wizard/prompts.py`**

Current function signature (line 34):
```python
def ask_field(
    number: int,
    icon: str,
    label: str,
    hint: str = "",
    default: str = "",
    examples: str = "",
) -> str:
```

Replace with:
```python
def ask_field(
    number: int,
    icon: str,
    label: str,
    hint: str = "",
    default: str = "",
    examples: str = "",
    validate=None,
) -> str:
```

Current `questionary.text(...)` call inside the function (lines 50-55):
```python
    value = questionary.text(
        message="",
        default=default,
        qmark="      ▸",
        style=Q_STYLE,
    ).ask()
```

Replace with:
```python
    kwargs = dict(
        message="",
        default=default,
        qmark="      ▸",
        style=Q_STYLE,
    )
    if validate is not None:
        kwargs["validate"] = validate
    value = questionary.text(**kwargs).ask()
```

**Step 2: Verify import works**

```bash
python -c "from wizard.prompts import ask_field; import inspect; sig = inspect.signature(ask_field); print(sig); assert 'validate' in sig.parameters"
```
Expected: Prints signature including `validate=None`.

**Step 3: Commit**

```bash
git add wizard/prompts.py
git commit -m "feat: add optional validate parameter to ask_field prompt"
```

---

## Task 6: Add validation error messages to all 6 i18n files

**Files:**
- Modify: `wizard/i18n/tr.json`
- Modify: `wizard/i18n/en.json`
- Modify: `wizard/i18n/de.json`
- Modify: `wizard/i18n/es.json`
- Modify: `wizard/i18n/fr.json`
- Modify: `wizard/i18n/it.json`

**Background:** Three new i18n keys needed under `steps.configure`: `port_invalid`, `version_invalid`, `site_name_invalid`.

**Step 1: Add keys to `wizard/i18n/tr.json`**

In the `"configure"` object, after `"cancelled": "Kurulum iptal edildi."`, add:
```json
      "port_invalid": "Geçerli bir port numarası girin (1024–65535)",
      "version_invalid": "Format geçersiz. Örnek: v16.7.3",
      "site_name_invalid": "Site adı en az bir nokta içermeli ve boşluk/geçersiz karakter içermemeli"
```

**Step 2: Add keys to `wizard/i18n/en.json`**

In the `"configure"` object, after `"cancelled": "Setup cancelled."`, add:
```json
      "port_invalid": "Enter a valid port number (1024–65535)",
      "version_invalid": "Invalid format. Example: v16.7.3",
      "site_name_invalid": "Site name must contain at least one dot and no spaces or invalid characters"
```

**Step 3: Add keys to `wizard/i18n/de.json`**

In the `"configure"` object, after `"cancelled": "Einrichtung abgebrochen."`, add:
```json
      "port_invalid": "Gültige Portnummer eingeben (1024–65535)",
      "version_invalid": "Ungültiges Format. Beispiel: v16.7.3",
      "site_name_invalid": "Site-Name muss mindestens einen Punkt enthalten und keine Leerzeichen oder ungültige Zeichen"
```

**Step 4: Add keys to `wizard/i18n/es.json`**

In the `"configure"` object, after `"cancelled": "Instalación cancelada."`, add:
```json
      "port_invalid": "Ingrese un número de puerto válido (1024–65535)",
      "version_invalid": "Formato inválido. Ejemplo: v16.7.3",
      "site_name_invalid": "El nombre del sitio debe contener al menos un punto y no tener espacios ni caracteres inválidos"
```

**Step 5: Add keys to `wizard/i18n/fr.json`**

In the `"configure"` object, after `"cancelled": "Installation annulée."`, add:
```json
      "port_invalid": "Entrez un numéro de port valide (1024–65535)",
      "version_invalid": "Format invalide. Exemple : v16.7.3",
      "site_name_invalid": "Le nom du site doit contenir au moins un point et pas d'espaces ni de caractères invalides"
```

**Step 6: Add keys to `wizard/i18n/it.json`**

In the `"configure"` object, after `"cancelled": "Installazione annullata."`, add:
```json
      "port_invalid": "Inserisci un numero di porta valido (1024–65535)",
      "version_invalid": "Formato non valido. Esempio: v16.7.3",
      "site_name_invalid": "Il nome del sito deve contenere almeno un punto e non avere spazi o caratteri non validi"
```

**Step 7: Verify all 6 files are valid JSON with the new keys**

```bash
python -c "
import json
keys = ['port_invalid', 'version_invalid', 'site_name_invalid']
for lang in ['tr', 'en', 'de', 'es', 'fr', 'it']:
    with open(f'wizard/i18n/{lang}.json', encoding='utf-8') as f:
        data = json.load(f)
    for key in keys:
        val = data['steps']['configure'][key]
        print(f'{lang}.{key}: {val}')
"
```
Expected: 18 lines, one per lang×key, no JSON errors.

**Step 8: Commit**

```bash
git add wizard/i18n/tr.json wizard/i18n/en.json wizard/i18n/de.json wizard/i18n/es.json wizard/i18n/fr.json wizard/i18n/it.json
git commit -m "i18n: add validation error messages for port, version, site_name in all 6 languages"
```

---

## Task 7: Add input validation to configure.py

**Files:**
- Modify: `wizard/steps/configure.py`

**Background:** Three fields need validators:
- `http_port`: numeric string, value 1024–65535
- `erpnext_version`: matches `v\d+\.\d+\.\d+`
- `site_name`: contains at least one dot, no spaces, only safe hostname chars

**Step 1: Add `re` import to `wizard/steps/configure.py`**

At the top of the file, the current imports are:
```python
import sys
from dataclasses import dataclass
```

Add `re` after `sys`:
```python
import re
import sys
from dataclasses import dataclass
```

**Step 2: Add validator functions before `run_configure`**

After the `Config` dataclass definition and before `def run_configure()`, add:

```python
def _validate_port(val: str) -> bool | str:
    if val.isdigit() and 1024 <= int(val) <= 65535:
        return True
    return t("steps.configure.port_invalid")


def _validate_version(val: str) -> bool | str:
    if re.fullmatch(r"v\d+\.\d+\.\d+", val):
        return True
    return t("steps.configure.version_invalid")


def _validate_site_name(val: str) -> bool | str:
    # Must contain a dot, no spaces, only hostname-safe characters
    if re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9\-\.]+", val) and "." in val:
        return True
    return t("steps.configure.site_name_invalid")
```

**Step 3: Wire validators to ask_field calls in `run_configure`**

Update the three `ask_field` calls to pass the validator:

`site_name` call — add `validate=_validate_site_name`:
```python
    site_name = ask_field(
        number=1,
        icon="🌐",
        label=t("steps.configure.site_name"),
        hint=t("steps.configure.site_name_hint"),
        examples="spaceflow.localhost · erp.localhost · myapp.localhost",
        default="mysite.localhost",
        validate=_validate_site_name,
    )
```

`erpnext_version` call — add `validate=_validate_version`:
```python
    erpnext_version = ask_field(
        number=2,
        icon="📦",
        label=t("steps.configure.erpnext_version"),
        hint=t("steps.configure.erpnext_version_hint"),
        default="v16.7.3",
        validate=_validate_version,
    )
```

`http_port` call — add `validate=_validate_port`:
```python
    http_port = ask_field(
        number=3,
        icon="🔌",
        label=t("steps.configure.http_port"),
        hint=t("steps.configure.http_port_hint"),
        default="8080",
        validate=_validate_port,
    )
```

**Step 4: Verify validators work correctly**

```bash
python -c "
import sys; sys.path.insert(0, '.')
from wizard.i18n import init as i18n_init
i18n_init('en')
from wizard.steps.configure import _validate_port, _validate_version, _validate_site_name

# Port tests
assert _validate_port('8080') == True
assert _validate_port('80') != True    # below 1024
assert _validate_port('99999') != True  # above 65535
assert _validate_port('abc') != True
assert _validate_port('1024') == True
assert _validate_port('65535') == True

# Version tests
assert _validate_version('v16.7.3') == True
assert _validate_version('v15.2.0') == True
assert _validate_version('16.7.3') != True  # missing v prefix
assert _validate_version('v16.7') != True   # missing patch
assert _validate_version('latest') != True

# Site name tests
assert _validate_site_name('mysite.localhost') == True
assert _validate_site_name('erp.mycompany.com') == True
assert _validate_site_name('noDotsHere') != True
assert _validate_site_name('has space.localhost') != True
assert _validate_site_name('my_site.localhost') != True  # underscore not allowed

print('All validator tests passed')
"
```
Expected: `All validator tests passed`

**Step 5: Commit**

```bash
git add wizard/steps/configure.py
git commit -m "feat: add input validation for site_name, erpnext_version, and http_port"
```

---

## Task 8: Final smoke test

**Step 1: Verify the full import chain is clean**

```bash
python -c "
from wizard.i18n import init as i18n_init
i18n_init('en')
from wizard.steps import TOTAL_STEPS, run_prerequisites, run_configure, run_env_file, run_docker, run_site
from wizard.prompts import ask_field, ask_password_field, confirm_action
print('All imports OK')
print('TOTAL_STEPS =', TOTAL_STEPS)
"
```
Expected:
```
All imports OK
TOTAL_STEPS = 5
```

**Step 2: Verify no duplicate TOTAL_STEPS definition remains**

```bash
grep -rn "^TOTAL_STEPS = 5" wizard/steps/
```
Expected: No output (only in `__init__.py` now, and it's imported there not defined as module-level in step files).

Actually verify the import is present in each step file:
```bash
grep -rn "TOTAL_STEPS" wizard/steps/
```
Expected: `__init__.py` has the definition, all other step files use it via `from . import TOTAL_STEPS`.

**Step 3: Verify no hardcoded `version-15` remains**

```bash
grep -rn "version-15" wizard/
```
Expected: No output.

**Step 4: Verify no bare `down -v` remains**

```bash
grep -rn "down -v" wizard/
```
Expected: No output.

**Step 5: Verify shlex import in site.py**

```bash
grep -n "import shlex" wizard/steps/site.py
```
Expected: One line showing `import shlex`.

**Step 6: Final commit**

```bash
git add -A
git status
git commit -m "chore: final smoke test verification — all improvements complete"
```

---

## Summary of Changes

| File | Change |
|------|--------|
| `wizard/steps/__init__.py` | Add `TOTAL_STEPS = 5` |
| `wizard/steps/prerequisites.py` | Remove local `TOTAL_STEPS`, import from `__init__` |
| `wizard/steps/configure.py` | Remove local `TOTAL_STEPS`, import from `__init__`; add `re` import; add 3 validator functions; wire validators to `ask_field` calls |
| `wizard/steps/env_file.py` | Remove local `TOTAL_STEPS`, import from `__init__`; add `_frappe_version()` helper; use dynamic FRAPPE_VERSION |
| `wizard/steps/docker.py` | Remove local `TOTAL_STEPS`, import from `__init__`; remove `-v` from `down` command |
| `wizard/steps/site.py` | Remove local `TOTAL_STEPS`, import from `__init__`; add `import shlex`; wrap all user values in `shlex.quote()` |
| `wizard/prompts.py` | Add `validate=None` parameter to `ask_field()` |
| `wizard/i18n/*.json` (×6) | Add 3 validation keys + update `cleaning` message |
