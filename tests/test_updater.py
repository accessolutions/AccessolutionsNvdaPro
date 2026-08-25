# -*- coding: utf-8 -*-
"""Tests indépendants des contrôles de mise à jour.

NVDA n’est pas disponible dans l’environnement CI. Les modules NVDA importés
par updater sont donc remplacés par de petits stubs avant le chargement ciblé
du module.
"""

import builtins
import hashlib
import importlib.util
import io
import os
import sys
import types
import unittest
import zipfile


builtins._ = lambda text: text

addon_handler = types.ModuleType("addonHandler")
addon_handler.AddonError = type("AddonError", (Exception,), {})
addon_handler.initTranslation = lambda: None
sys.modules["addonHandler"] = addon_handler

global_vars = types.ModuleType("globalVars")
global_vars.appArgs = types.SimpleNamespace(secure=False)
sys.modules["globalVars"] = global_vars


_UPDATER_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "globalPlugins",
    "AccessolutionsNvdaPro",
    "updater.py",
)
_spec = importlib.util.spec_from_file_location("updater_under_test", _UPDATER_PATH)
updater = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(updater)


class UpdaterTests(unittest.TestCase):

    @staticmethod
    def _package(version="2026.08.26.0001", name="AccessolutionsNVDAPro"):
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as package:
            package.writestr(
                "manifest.ini",
                "name = %s\nversion = %s\n" % (name, version),
            )
            package.writestr("globalPlugins/example.py", "# test\n")
        return output.getvalue()

    def test_sha256_parser_rejects_ambiguous_content(self):
        first = "a" * 64
        second = "b" * 64
        self.assertIsNone(updater._parse_sha256(first + "\n" + second))

    def test_sha256_parser_matches_requested_asset(self):
        first = "a" * 64
        second = "b" * 64
        content = "%s  other.nvda-addon\n%s  AccessolutionsNVDAPro-1.nvda-addon\n" % (
            first,
            second,
        )
        self.assertEqual(
            second,
            updater._parse_sha256(
                content,
                expected_filename="AccessolutionsNVDAPro-1.nvda-addon",
            ),
        )

    def test_package_version_must_match(self):
        package = self._package()
        updater._validate_package(package, "2026.08.26.0001")
        with self.assertRaises(updater.UpdateError):
            updater._validate_package(package, "2026.08.27.0001")

    def test_download_validates_package_before_writing(self):
        package = self._package()
        update = types.SimpleNamespace(
            asset_url="https://github.com/Accessolutions/AccessolutionsNVDAPro/releases/download/test/package.nvda-addon",
            sha256=hashlib.sha256(package).hexdigest(),
            version="2026.08.26.0001",
        )
        old_fetch = updater._fetch_bytes
        old_can_write = updater._can_write_to_disk
        updater._fetch_bytes = lambda url, cancellation=None: package
        updater._can_write_to_disk = lambda: True
        try:
            path = updater.download_update(update)
            try:
                self.assertTrue(os.path.isfile(path))
            finally:
                updater.remove_temporary_file(path)
        finally:
            updater._fetch_bytes = old_fetch
            updater._can_write_to_disk = old_can_write

    def test_download_rejects_package_with_wrong_version(self):
        package = self._package(version="2026.08.26.0002")
        update = types.SimpleNamespace(
            asset_url="https://github.com/Accessolutions/AccessolutionsNVDAPro/releases/download/test/package.nvda-addon",
            sha256=hashlib.sha256(package).hexdigest(),
            version="2026.08.26.0001",
        )
        old_fetch = updater._fetch_bytes
        old_can_write = updater._can_write_to_disk
        updater._fetch_bytes = lambda url, cancellation=None: package
        updater._can_write_to_disk = lambda: True
        try:
            with self.assertRaises(updater.UpdateError):
                updater.download_update(update)
        finally:
            updater._fetch_bytes = old_fetch
            updater._can_write_to_disk = old_can_write


if __name__ == "__main__":
    unittest.main()
