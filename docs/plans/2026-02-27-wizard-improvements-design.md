# ERPNext Setup Wizard — Improvements Design
Date: 2026-02-27

## Goal
Perfect the existing 5-step wizard: fix all bugs, add input validation, improve security and code quality — without adding new features or files.

## Approach
Targeted in-place improvements across existing files. No new modules.

## Changes

### 1. Shared constant — `wizard/steps/__init__.py`
- Add `TOTAL_STEPS = 5` here
- Remove the duplicate `TOTAL_STEPS = 5` from all 5 step files
- Each step file imports from `__init__.py`

### 2. `wizard/steps/env_file.py` — Dynamic FRAPPE_VERSION
- Parse major version from `cfg.erpnext_version` (e.g. "v16.7.3" → "16" → "version-16")
- Fallback to "version-16" if parse fails
- Fix: hardcoded `FRAPPE_VERSION=version-15` was wrong for v16+ users

### 3. `wizard/steps/docker.py` — Remove destructive `-v` flag
- Change `down -v` to `down` (preserves named volumes / existing data)
- Update i18n message to clarify data is preserved
- Fix: `-v` was silently deleting all database data on every re-run

### 4. `wizard/steps/site.py` — Shell-safe interpolation
- Wrap `cfg.site_name`, `cfg.db_password`, `cfg.admin_password` in `shlex.quote()`
- Fix: special characters (spaces, $, ', ") in passwords could break or inject commands

### 5. `wizard/steps/configure.py` — Input validation
- `http_port`: must be numeric, 1024–65535
- `erpnext_version`: must match `v\d+\.\d+\.\d+`
- `site_name`: must contain at least one dot, no spaces/special chars

### 6. `wizard/prompts.py` — `ask_field` validate parameter
- Add optional `validate` callable parameter to `ask_field()`
- Pass it through to `questionary.text(validate=validate)`

### 7. i18n — Validation error messages (all 6 languages)
- Add keys under `configure`: `port_invalid`, `version_invalid`, `site_name_invalid`
- Files: tr.json, en.json, de.json, es.json, fr.json, it.json

## Files Modified
- `wizard/steps/__init__.py`
- `wizard/steps/prerequisites.py`
- `wizard/steps/configure.py`
- `wizard/steps/env_file.py`
- `wizard/steps/docker.py`
- `wizard/steps/site.py`
- `wizard/prompts.py`
- `wizard/i18n/tr.json`
- `wizard/i18n/en.json`
- `wizard/i18n/de.json`
- `wizard/i18n/es.json`
- `wizard/i18n/fr.json`
- `wizard/i18n/it.json`

## No New Files
All changes are in-place edits to existing files.
