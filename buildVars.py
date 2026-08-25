"""Paramètres de construction de l’extension Accessolutions NVDA Pro."""

addon_name = "AccessolutionsNVDAPro"
base_language = "fr"
source_directories = ("appModules", "globalPlugins", "doc")
python_sources = (
    "appModules/*.py",
    "globalPlugins/*.py",
    "globalPlugins/AccessolutionsNvdaPro/*.py",
)
i18n_sources = python_sources
excluded_suffixes = (".pyc", ".pyo")
excluded_directories = ("__pycache__",)
