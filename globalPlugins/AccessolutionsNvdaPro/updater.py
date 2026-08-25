# -*- coding: utf-8 -*-

"""Recherche et installation sécurisées des mises à jour Accessolutions NVDA Pro."""

import hashlib
import hmac
import io
import json
import logging
import os
import re
import shutil
import tempfile
import threading
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
import zipfile

import addonHandler
import globalVars

addonHandler.initTranslation()

log = logging.getLogger("AccessolutionsNVDAPro.updater")

# Le dépôt doit être public pour que l'API GitHub soit accessible sans jeton.
REPOSITORY = "Accessolutions/AccessolutionsNVDAPro"
ADDON_NAME = "AccessolutionsNVDAPro"
RELEASES_URL = "https://api.github.com/repos/%s/releases?per_page=100" % REPOSITORY
_USER_AGENT = "AccessolutionsNVDAPro updater"
_NETWORK_TIMEOUT = 30
_MAX_RESPONSE_SIZE = 16 * 1024 * 1024
_MAX_REDIRECTS = 5
_READ_CHUNK_SIZE = 64 * 1024
_ALLOWED_HOSTS = frozenset(
	{
		"api.github.com",
		"github.com",
		"www.github.com",
		"raw.githubusercontent.com",
		"objects.githubusercontent.com",
		"release-assets.githubusercontent.com",
		"github-releases.githubusercontent.com",
		"github-production-release-asset-2e65be.s3.amazonaws.com",
	}
)
_VERSION_PATTERN = re.compile(r"^(?:\d{8}(?:\.\d+)*|\d{4}(?:\.\d+){1,5})$")
_ASSET_VERSION_PATTERN = re.compile(
	r"^accessolutionsnvdapro-(?P<version>(?:\d{8}(?:\.\d+)*|\d{4}(?:\.\d+){1,5}))\.nvda-addon$",
	re.IGNORECASE,
)
_SHA256_LINE_PATTERN = re.compile(
	r"^\s*(?:[-*]\s*)?(?:sha[- ]?256\s*[:=]\s*)?"
	r"(?P<digest>[0-9a-f]{64})(?:\s+(?P<filename>\*?\S+))?\s*$",
	re.IGNORECASE,
)


class UpdateInfo:
	def __init__(self, version, release_name, release_url, asset_name, asset_url, sha256, sha256_url, notes):
		self.version = version
		self.release_name = release_name
		self.release_url = release_url
		self.asset_name = asset_name
		self.asset_url = asset_url
		self.sha256 = sha256
		self.sha256_url = sha256_url
		self.notes = notes


class UpdateError(Exception):
	"""Erreur de recherche, de téléchargement ou de validation d'une mise à jour."""


def _version_key(version):
	"""Construit une clé comparable pour les versions datées de l'extension."""
	text = str(version or "").strip().lstrip("vV")
	parts = re.findall(r"\d+", text)
	if not parts:
		return (0,)
	numbers = [int(part) for part in parts]
	if len(parts[0]) == 8:
		date_part = parts[0]
		return (int(date_part[:4]), int(date_part[4:6]), int(date_part[6:8]), *numbers[1:])
	return tuple(numbers)


def is_newer_version(candidate, current):
	return _version_key(candidate) > _version_key(current)


def _can_write_to_disk():
	"""Refuse les écritures lorsque NVDA est en mode sécurisé."""
	try:
		import NVDAState
		should_write = getattr(NVDAState, "shouldWriteToDisk", None)
		if should_write is not None:
			return bool(should_write())
	except (ImportError, AttributeError, TypeError):
		pass
	return not getattr(globalVars.appArgs, "secure", False)


class _Cancellation:
	"""Annulation coopérative d’une opération réseau en cours."""

	def __init__(self):
		self.event = threading.Event()
		self._lock = threading.Lock()
		self._response = None

	def cancel(self):
		self.event.set()
		with self._lock:
			response = self._response
		if response is not None:
			try:
				response.close()
			except (AttributeError, OSError, ValueError):
				pass

	def register_response(self, response):
		with self._lock:
			if self.event.is_set():
				should_close = True
			else:
				self._response = response
				should_close = False
		if should_close:
			try:
				response.close()
			except (AttributeError, OSError, ValueError):
				pass

	def unregister_response(self, response):
		with self._lock:
			if self._response is response:
				self._response = None


def _check_cancelled(cancellation):
	if cancellation is not None and cancellation.event.is_set():
		raise UpdateError(_("L’opération de mise à jour a été annulée."))


def _validate_fetch_url(url, kind="adresse"):
	try:
		parsed = urlsplit(url)
		hostname = parsed.hostname
		port = parsed.port
	except ValueError as error:
		raise UpdateError(_("Adresse %s invalide : %s") % (kind, error))
	if parsed.scheme.lower() != "https":
		raise UpdateError(_("Seules les adresses HTTPS sont acceptées : %s") % url)
	if parsed.username or parsed.password or not hostname or port not in (None, 443):
		raise UpdateError(_("Adresse %s non sûre : %s") % (kind, url))
	host = hostname.lower().rstrip(".")
	if host not in _ALLOWED_HOSTS:
		raise UpdateError(_("Domaine %s non autorisé pour une mise à jour : %s") % (host, url))


class _SafeRedirectHandler(HTTPRedirectHandler):
	"""Limite les redirections à HTTPS et aux domaines GitHub nécessaires."""

	def __init__(self, cancellation=None):
		super(_SafeRedirectHandler, self).__init__()
		self._redirect_count = 0
		self._cancellation = cancellation

	def redirect_request(self, request, file, code, message, headers, new_url):
		_check_cancelled(self._cancellation)
		if self._redirect_count >= _MAX_REDIRECTS:
			raise UpdateError(
				_("Trop de redirections lors de la récupération de %s") % request.full_url
			)
		_validate_fetch_url(new_url, kind="redirection")
		self._redirect_count += 1
		return super(_SafeRedirectHandler, self).redirect_request(
			request, file, code, message, headers, new_url
		)


def _fetch_bytes(url, cancellation=None):
	_validate_fetch_url(url)
	_check_cancelled(cancellation)

	opener = build_opener(ProxyHandler(), _SafeRedirectHandler(cancellation))
	request = Request(
		url,
		headers={
			"Accept": "application/vnd.github+json",
			"User-Agent": _USER_AGENT,
		},
	)
	try:
		with opener.open(request, timeout=_NETWORK_TIMEOUT) as response:
			if cancellation is not None:
				cancellation.register_response(response)
			try:
				data = bytearray()
				while True:
					_check_cancelled(cancellation)
					chunk = response.read(
						min(_READ_CHUNK_SIZE, _MAX_RESPONSE_SIZE + 1 - len(data))
					)
					data.extend(chunk)
					if len(data) > _MAX_RESPONSE_SIZE:
						raise UpdateError(_("La réponse reçue est trop volumineuse"))
					if not chunk:
						break
				return bytes(data)
			finally:
				if cancellation is not None:
					cancellation.unregister_response(response)
	except UpdateError:
		raise
	except (HTTPError, URLError, OSError, ValueError) as error:
		if cancellation is not None and cancellation.event.is_set():
			raise UpdateError(_("L’opération de mise à jour a été annulée."))
		raise UpdateError(_("Impossible de récupérer %s : %s") % (url, error))


def _parse_sha256(data, expected_filename=None):
	"""Extrait une empreinte SHA-256 d’une ligne de somme conventionnelle.

	Les contenus ambigus sont refusés. Si plusieurs empreintes sont publiées,
	le nom du paquet attendu doit apparaître sur la ligne correspondante.
	"""
	if isinstance(data, bytes):
		try:
			data = data.decode("utf-8")
		except UnicodeDecodeError:
			return None
	if not isinstance(data, str):
		return None
	entries = []
	for raw_line in data.splitlines():
		line = raw_line.strip().strip("`")
		match = _SHA256_LINE_PATTERN.fullmatch(line)
		if match:
			entries.append((
				match.group("digest").lower(),
				(match.group("filename") or "").lstrip("*"),
			))
	if not entries:
		return None

	all_digests = {digest for digest, _ in entries}
	if expected_filename:
		expected = os.path.basename(str(expected_filename)).lower()
		named_digests = {
			digest for digest, filename in entries
			if filename and os.path.basename(filename).lower() == expected
		}
		if len(named_digests) == 1:
			return next(iter(named_digests))
		if named_digests:
			return None
	if len(all_digests) == 1:
		return next(iter(all_digests))
	return None


def _manifest_value(manifest, key):
	pattern = re.compile(r"^\s*%s\s*=\s*(.*?)\s*$" % re.escape(key), re.IGNORECASE)
	for raw_line in manifest.splitlines():
		match = pattern.match(raw_line.lstrip("\ufeff"))
		if match:
			return match.group(1).strip().strip("\"'")
	return None


def _inspect_package(data):
	try:
		with zipfile.ZipFile(io.BytesIO(data)) as package:
			if package.namelist().count("manifest.ini") != 1:
				raise UpdateError(_("Le paquet ne contient pas un manifeste unique."))
			manifest = package.read("manifest.ini").decode("utf-8")
	except UpdateError:
		raise
	except (UnicodeDecodeError, KeyError, OSError, zipfile.BadZipFile) as error:
		raise UpdateError(_("Le paquet téléchargé est invalide : %s") % error)
	name = _manifest_value(manifest, "name")
	version = _manifest_value(manifest, "version")
	if not name or not version:
		raise UpdateError(_("Le manifeste du paquet est incomplet."))
	return name, version


def _validate_package(data, expected_version):
	name, version = _inspect_package(data)
	if name != ADDON_NAME:
		raise UpdateError(_("Le paquet téléchargé ne correspond pas à Accessolutions NVDA Pro"))
	if version != str(expected_version).strip():
		raise UpdateError(
			_("Incohérence de version : le paquet contient %s au lieu de %s")
			% (version, expected_version)
		)
	return name, version


def _release_version(release, asset_name):
	for value in (release.get("tag_name"), release.get("name")):
		version = str(value or "").strip().lstrip("vV")
		if _VERSION_PATTERN.fullmatch(version):
			return version
	match = _ASSET_VERSION_PATTERN.fullmatch(asset_name.strip())
	return match.group("version") if match else ""


def _find_assets(release):
	assets = [asset for asset in release.get("assets") or [] if isinstance(asset, dict)]
	addon_assets = [
		asset for asset in assets
		if str(asset.get("name", "")).lower().endswith(".nvda-addon")
		and str(asset.get("browser_download_url", "")).startswith("https://")
	]
	if not addon_assets:
		raise UpdateError(_("La release ne contient aucun module NVDA"))
	addon_asset = next(
		(
			asset for asset in addon_assets
			if str(asset.get("name", "")).lower().startswith(ADDON_NAME.lower() + "-")
		),
		addon_assets[0],
	)
	addon_name = str(addon_asset.get("name", ""))
	hash_asset = next(
		(
			asset for asset in assets
			if str(asset.get("name", "")).lower() in (
				addon_name.lower() + ".sha256",
				addon_name.lower() + ".sha256.txt",
			)
			and str(asset.get("browser_download_url", "")).startswith("https://")
		),
		None,
	)
	return addon_asset, hash_asset


def check_for_update(current_version, cancellation=None):
	"""Retourne la dernière release stable vérifiée, ou None si elle est absente."""
	try:
		data = _fetch_bytes(RELEASES_URL, cancellation=cancellation)
		releases = json.loads(data.decode("utf-8"))
	except (ValueError, UnicodeDecodeError) as error:
		raise UpdateError(_("Réponse GitHub invalide : %s") % error)
	if not isinstance(releases, list):
		raise UpdateError(_("GitHub a renvoyé une liste de releases invalide"))

	candidates = []
	for release in releases:
		_check_cancelled(cancellation)
		if not isinstance(release, dict) or release.get("draft") or release.get("prerelease"):
			continue
		try:
			addon_asset, hash_asset = _find_assets(release)
		except UpdateError:
			continue
		version = _release_version(release, str(addon_asset.get("name", "")))
		if version and is_newer_version(version, current_version):
			candidates.append((_version_key(version), release, version, addon_asset, hash_asset))

	for _, release, version, addon_asset, hash_asset in sorted(
		candidates, key=lambda item: item[0], reverse=True
	):
		try:
			hash_url = hash_asset.get("browser_download_url") if hash_asset else None
			addon_name = str(addon_asset.get("name", ""))
			sha256 = (
				_parse_sha256(
					_fetch_bytes(hash_url, cancellation=cancellation),
					expected_filename=addon_name,
				)
				if hash_url
				else None
			)
			if not sha256:
				sha256 = _parse_sha256(
					release.get("body", ""), expected_filename=addon_name
				)
			if not sha256:
				raise UpdateError(_("La release ne publie pas d'empreinte SHA-256"))
			return UpdateInfo(
				version=version,
				release_name=str(release.get("name") or version),
				release_url=str(release.get("html_url") or ""),
				asset_name=str(addon_asset.get("name")),
				asset_url=str(addon_asset.get("browser_download_url")),
				sha256=sha256,
				sha256_url=hash_url,
				notes=str(release.get("body") or ""),
			)
		except UpdateError:
			log.warning("Release Accessolutions NVDA Pro ignorée : %s", version, exc_info=True)
	return None


def download_update(update, cancellation=None):
	if not _can_write_to_disk():
		raise UpdateError(_("Les mises à jour sont désactivées en mode sécurisé"))
	_check_cancelled(cancellation)
	data = _fetch_bytes(update.asset_url, cancellation=cancellation)
	digest = hashlib.sha256(data).hexdigest()
	expected_sha256 = str(update.sha256 or "").strip().lower()
	if not re.fullmatch(r"[0-9a-f]{64}", expected_sha256):
		raise UpdateError(_("L'empreinte SHA-256 publiée est invalide"))
	if not hmac.compare_digest(digest.lower(), expected_sha256):
		raise UpdateError(_("L'empreinte SHA-256 du module téléchargé est incorrecte"))
	_validate_package(data, update.version)
	_check_cancelled(cancellation)
	fd, path = tempfile.mkstemp(prefix="AccessolutionsNVDAPro-", suffix=".nvda-addon")
	try:
		with os.fdopen(fd, "wb") as output:
			output.write(data)
	except Exception:
		try:
			os.unlink(path)
		except OSError:
			pass
		raise
	return path


def remove_temporary_file(path):
	if not path:
		return
	try:
		os.unlink(path)
	except OSError:
		pass


def _installed_addon():
	try:
		return addonHandler.getCodeAddon()
	except (addonHandler.AddonError, AttributeError):
		return None


def _pending_install_path():
	addon = _installed_addon()
	if addon is None:
		return None
	return os.path.join(os.path.dirname(os.path.normpath(addon.path)), ADDON_NAME + ".pendingInstall")


def _remove_stale_pending_install():
	path = _pending_install_path()
	if path and os.path.isdir(path):
		shutil.rmtree(path, ignore_errors=True)


def _request_remove_installed_addon():
	addon = _installed_addon()
	if addon is None or getattr(addon, "isPendingRemove", False):
		return
	try:
		addon.requestRemove()
	except Exception:
		log.warning("Impossible de planifier la suppression de l'ancienne version", exc_info=True)


def install_package(path, expected_version=None):
	"""Installe un paquet déjà téléchargé et vérifié par l'API NVDA."""
	if not _can_write_to_disk():
		raise UpdateError(_("L'installation est désactivée en mode sécurisé"))
	if not path or not os.path.isfile(path):
		raise UpdateError(_("Le paquet de mise à jour est introuvable"))
	bundle_type = getattr(addonHandler, "AddonBundle", None)
	installer = getattr(addonHandler, "installAddonBundle", None)
	if bundle_type is not None and installer is not None:
		try:
			bundle = bundle_type(path)
		except Exception as error:
			raise UpdateError(_("Le paquet téléchargé est invalide : %s") % error)
		manifest = getattr(bundle, "manifest", {})
		if manifest.get("name") != ADDON_NAME:
			raise UpdateError(_("Le paquet téléchargé ne correspond pas à Accessolutions NVDA Pro"))
		bundled_version = str(manifest.get("version") or "").strip()
		if not bundled_version:
			raise UpdateError(_("Le manifeste du paquet ne contient pas de version"))
		if expected_version is not None and bundled_version != str(expected_version).strip():
			raise UpdateError(
				_("Incohérence de version : le paquet contient %s au lieu de %s")
				% (bundled_version, expected_version)
			)
		_remove_stale_pending_install()
		_request_remove_installed_addon()
		installer(bundle)
		return
	legacy_installer = getattr(addonHandler, "installAddonPackage", None)
	if legacy_installer is not None:
		with open(path, "rb") as package_file:
			data = package_file.read(_MAX_RESPONSE_SIZE + 1)
		if len(data) > _MAX_RESPONSE_SIZE:
			raise UpdateError(_("Le paquet de mise à jour est trop volumineux"))
		name, version = _inspect_package(data)
		if name != ADDON_NAME or not version:
			raise UpdateError(_("Le paquet téléchargé ne correspond pas à Accessolutions NVDA Pro"))
		if expected_version is not None and version != str(expected_version).strip():
			raise UpdateError(
				_("Incohérence de version : le paquet contient %s au lieu de %s")
				% (version, expected_version)
			)
		legacy_installer(path)
		return
	raise UpdateError(_("Cette version de NVDA ne fournit pas d'API d'installation d'extension"))


class UpdateManager:
	"""Exécute les opérations réseau hors du thread principal de NVDA."""

	def __init__(self):
		self._lock = threading.Lock()
		self._workers = set()
		self._stopped = threading.Event()
		self._cancellations = {}

	def _start(self, target, callback):
		with self._lock:
			if self._stopped.is_set():
				return False
			self._workers = {worker for worker in self._workers if worker.is_alive()}
			if self._workers:
				return False
			cancellation = _Cancellation()
			worker = threading.Thread(
				target=target,
				args=(callback, cancellation),
				name="Accessolutions NVDA Pro updater",
				daemon=True,
			)
			self._workers.add(worker)
			self._cancellations[worker] = cancellation
		worker.start()
		return True

	def check_async(self, current_version, callback, manual=False):
		def run(done, cancellation):
			try:
				result = check_for_update(current_version, cancellation=cancellation)
			except Exception as error:
				log.debug("Échec de la recherche de mise à jour", exc_info=True)
				with self._lock:
					self._workers.discard(threading.current_thread())
					self._cancellations.pop(threading.current_thread(), None)
				done(None, error, manual)
			else:
				with self._lock:
					self._workers.discard(threading.current_thread())
					self._cancellations.pop(threading.current_thread(), None)
				done(result, None, manual)
		return self._start(run, callback)

	def download_async(self, update, callback):
		def run(done, cancellation):
			try:
				path = download_update(update, cancellation=cancellation)
			except Exception as error:
				log.debug("Échec du téléchargement de la mise à jour", exc_info=True)
				with self._lock:
					self._workers.discard(threading.current_thread())
					self._cancellations.pop(threading.current_thread(), None)
				done(None, error)
			else:
				with self._lock:
					self._workers.discard(threading.current_thread())
					self._cancellations.pop(threading.current_thread(), None)
				done(path, None)
		return self._start(run, callback)

	def terminate(self):
		self._stopped.set()
		with self._lock:
			cancellations = list(self._cancellations.values())
		for cancellation in cancellations:
			cancellation.cancel()
