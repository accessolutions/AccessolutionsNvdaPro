# Construire l’extension

Le dépôt utilise SCons pour compiler les traductions et créer le paquet NVDA.

## Prérequis

- Python 3.10 ou une version plus récente ;
- SCons (`python -m pip install scons`).

Aucun outil gettext externe n’est nécessaire pour le build : le script SCons
compile directement les fichiers `locale/*/LC_MESSAGES/nvda.po` en fichiers MO.

## Commandes

Depuis la racine du dépôt :

- `scons` construit `package/AccessolutionsNVDAPro-<version>.nvda-addon` et son
  fichier `.sha256` ;
- `scons version=2026.08.26.0001` construit une version donnée ;
- `scons pot` extrait les chaînes localisables dans `build/` ;
- `scons -c` supprime les fichiers générés.

Les catalogues PO doivent rester dans `locale/<langue>/LC_MESSAGES/nvda.po`.
Seuls les fichiers MO compilés sont inclus dans le paquet final.
