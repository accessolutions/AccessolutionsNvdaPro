"""Recherche et installation sécurisées des mises à jour Accessolutions NVDA Pro."""

import hashlib
import hmac
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

import addonHandler
import globalVars

log = logging.getLogger("AccessolutionsNVDAPro.updater")

# Le dépôt doit être public pour que l'API GitHub soit accessible sans jeton.
REPOSITORY = "Accessolutions/AccessolutionsNVDAPro"
ADDON_NAME = "AccessolutionsNVDAPro"
RELEASES_URL = "https://api.github.com/repos/%s/releases?per_page=100" % REPOSITORY
_USER_AGENT = "AccessolutionsNVDAPro updater"
_NETWORK_TIMEOUT = 30
_MAX_RESPONSE_SIZE = 16 * 1024 * 1024
_MAX_REDIRECTS = 5
_VERSION_PATTERN = re.compile(r"^(?:\d{8}(?:\.\d+)*|\d{4}(?:\.\d+){1,5})$")
_ASSET_VERSION_PATTERN = re.compile(
	r"^accessolutionsnvdapro-(?P<version>(?:\d{8}(?:\.\d+)*|\d{4}(?:\.\d+){1,5}))\.nvda-addon$",
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


def _fetch_bytes(url):
	if urlsplit(url).scheme.lower() != "https":
		raise UpdateError("Seules les adresses HTTPS sont acceptées : %s" % url)

	class HttpsRedirectHandler(HTTPRedirectHandler):
		def redirect_request(self, request, file, code, message, headers, new_url):
			if urlsplit(new_url).scheme.lower() != "https":
				raise UpdateError("Une redirection non HTTPS a été refusée : %s" % new_url)
			return super(HttpsRedirectHandler, self).redirect_request(
				request, file, code, message, headers, new_url
			)

	opener = build_opener(ProxyHandler(), HttpsRedirectHandler())
	request = Request(
		url,
		headers={
			"Accept": "application/vnd.github+json",
			"User-Agent": _USER_AGENT,
		},
	)
	for _ in range(_MAX_REDIRECTS + 1):
		try:
			with opener.open(request, timeout=_NETWORK_TIMEOUT) as response:
				data = response.read(_MAX_RESPONSE_SIZE + 1)
		except (HTTPError, URLError, OSError) as error:
			raise UpdateError("Impossible de récupérer %s : %s" % (url, error))
		if len(data) > _MAX_RESPONSE_SIZE:
			raise UpdateError("La réponse reçue est trop volumineuse")
		return data
	raise UpdateError("Trop de redirections lors de la récupération de %s" % url)


def _parse_sha256(data):
	if isinstance(data, bytes):
		data = data.decode("ascii", errors="ignore")
	match = re.search(r"(?i)\b([0-9a-f]{64})\b", data)
	return match.group(1).lower() if match else None


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
		raise UpdateError("La release ne contient aucun module NVDA")
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


def check_for_update(current_version):
	"""Retourne la dernière release stable vérifiée, ou None si elle est absente."""
	try:
		data = _fetch_bytes(RELEASES_URL)
		releases = json.loads(data.decode("utf-8"))
	except (ValueError, UnicodeDecodeError) as error:
		raise UpdateError("Réponse GitHub invalide : %s" % error)
	if not isinstance(releases, list):
		raise UpdateError("GitHub a renvoyé une liste de releases invalide")

	candidates = []
	for release in releases:
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
			sha256 = _parse_sha256(_fetch_bytes(hash_url)) if hash_url else None
			if not sha256:
				sha256 = _parse_sha256(release.get("body", ""))
			if not sha256:
				raise UpdateError("La release ne publie pas d'empreinte SHA-256")
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


def download_update(update):
	if not _can_write_to_disk():
		raise UpdateError("Les mises à jour sont désactivées en mode sécurisé")
	data = _fetch_bytes(update.asset_url)
	digest = hashlib.sha256(data).hexdigest()
	if not hmac.compare_digest(digest.lower(), update.sha256.lower()):
		raise UpdateError("L'empreinte SHA-256 du module téléchargé est incorrecte")
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


def install_package(path):
	"""Installe un paquet déjà téléchargé et vérifié par l'API NVDA."""
	if not _can_write_to_disk():
		raise UpdateError("L'installation est désactivée en mode sécurisé")
	if not path or not os.path.isfile(path):
		raise UpdateError("Le paquet de mise à jour est introuvable")
	bundle_type = getattr(addonHandler, "AddonBundle", None)
	installer = getattr(addonHandler, "installAddonBundle", None)
	if bundle_type is not None and installer is not None:
		bundle = bundle_type(path)
		if bundle.manifest.get("name") != ADDON_NAME:
			raise UpdateError("Le paquet téléchargé ne correspond pas à Accessolutions NVDA Pro")
		_remove_stale_pending_install()
		_request_remove_installed_addon()
		installer(bundle)
		return
	legacy_installer = getattr(addonHandler, "installAddonPackage", None)
	if legacy_installer is not None:
		legacy_installer(path)
		return
	raise UpdateError("Cette version de NVDA ne fournit pas d'API d'installation d'extension")


class UpdateManager:
	"""Exécute les opérations réseau hors du thread principal de NVDA."""

	def __init__(self):
		self._lock = threading.Lock()
		self._workers = set()
		self._stopped = threading.Event()

	def _start(self, target, callback):
		with self._lock:
			if self._stopped.is_set():
				return False
			self._workers = {worker for worker in self._workers if worker.is_alive()}
			if self._workers:
				return False
			worker = threading.Thread(
				target=target,
				args=(callback,),
				name="Accessolutions NVDA Pro updater",
				daemon=True,
			)
			self._workers.add(worker)
		worker.start()
		return True

	def check_async(self, current_version, callback, manual=False):
		def run(done):
			try:
				result = check_for_update(current_version)
			except Exception as error:
				log.debug("Échec de la recherche de mise à jour", exc_info=True)
				with self._lock:
					self._workers.discard(threading.current_thread())
				done(None, error, manual)
			else:
				with self._lock:
					self._workers.discard(threading.current_thread())
				done(result, None, manual)
		return self._start(run, callback)

	def download_async(self, update, callback):
		def run(done):
			try:
				path = download_update(update)
			except Exception as error:
				log.debug("Échec du téléchargement de la mise à jour", exc_info=True)
				with self._lock:
					self._workers.discard(threading.current_thread())
				done(None, error)
			else:
				with self._lock:
					self._workers.discard(threading.current_thread())
				done(path, None)
		return self._start(run, callback)

	def terminate(self):
		self._stopped.set()
