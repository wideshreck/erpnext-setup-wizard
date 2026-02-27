"""Registry of optional Frappe apps available for installation."""

# Each tuple: (repo_name, display_name, i18n_description_key)
# repo_name is the GitHub repo under github.com/frappe/{repo_name}
# i18n_description_key resolves via t("apps.{repo_name}")
OPTIONAL_APPS: list[tuple[str, str, str]] = [
    ("hrms",           "HRMS",           "apps.hrms"),
    ("payments",       "Payments",       "apps.payments"),
    ("healthcare",     "Healthcare",     "apps.healthcare"),
    ("education",      "Education",      "apps.education"),
    ("lending",        "Lending",        "apps.lending"),
    ("webshop",        "Webshop",        "apps.webshop"),
    ("print_designer", "Print Designer", "apps.print_designer"),
    ("wiki",           "Wiki",           "apps.wiki"),
]
