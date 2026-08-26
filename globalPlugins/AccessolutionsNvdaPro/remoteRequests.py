# -*- coding: utf-8 -*-

import os
import globalPluginHandler
from urllib.parse import urlencode

import addonHandler
import config
import gui
import ui
import wx
from logHandler import log

addonHandler.initTranslation()

REMOTE_ENDPOINT = "nvdaremote://nvdaremote.accessolutions.fr/"

_MISSING = object()
_STATE_DISCONNECTED = "disconnected"
_STATE_CONNECTING = "connecting"
_STATE_SLAVE = "slave"
_STATE_MASTER = "master"
_STATE_CONNECTED = "connected"
_STATE_UNKNOWN = "unknown"
_ACTIVE_STATES = {
	_STATE_CONNECTING,
	_STATE_SLAVE,
	_STATE_MASTER,
	_STATE_CONNECTED,
}

_CONNECTING_FLAGS = ("isConnecting", "connecting", "is_connecting")
_CONNECTED_FLAGS = ("isConnected", "is_connected", "connected")
_SLAVE_FLAGS = (
	"isConnectedAsFollower",
	"is_connected_as_follower",
	"isSlave",
	"is_slave",
)
_MASTER_FLAGS = (
	"isConnectedAsLeader",
	"is_connected_as_leader",
	"isMaster",
	"is_master",
)
_SLAVE_SESSIONS = ("followerSession", "slave_session")
_MASTER_SESSIONS = ("leaderSession", "master_session")
_TELENVDA_IDENTIFIERS = (
	"telenvda",
	"telenvdaaccessolutions",
	"telenvda_accessolutions",
)
_LEGACY_REMOTE_IDENTIFIERS = ("remoteclient",)


def _as_bool(value):
	if isinstance(value, str):
		return value.strip().casefold() in ("1", "true", "yes", "on")
	return bool(value)


def _get_attribute(owner, name):
	try:
		return getattr(owner, name)
	except Exception:
		return _MISSING


def _read_flags(owner, names):
	found = False
	for name in names:
		value = _get_attribute(owner, name)
		if value is _MISSING:
			continue
		try:
			if callable(value):
				value = value()
		except Exception:
			continue
		found = True
		if _as_bool(value):
			return True, True
	return found, False


def _read_sessions(owner, names):
	found = False
	active = False
	for name in names:
		value = _get_attribute(owner, name)
		if value is _MISSING:
			continue
		found = True
		if value is not None:
			active = True
	return found, active


def _connection_state(owner):
	"""Retourne un état normalisé sans dépendre d'une seule API distante."""
	connecting_found, connecting = _read_flags(owner, _CONNECTING_FLAGS)
	connected_found, connected = _read_flags(owner, _CONNECTED_FLAGS)
	slave_flag_found, slave_flag = _read_flags(owner, _SLAVE_FLAGS)
	master_flag_found, master_flag = _read_flags(owner, _MASTER_FLAGS)
	slave_session_found, slave_session = _read_sessions(owner, _SLAVE_SESSIONS)
	master_session_found, master_session = _read_sessions(owner, _MASTER_SESSIONS)

	if not any(
		(
			connecting_found,
			connected_found,
			slave_flag_found,
			master_flag_found,
			slave_session_found,
			master_session_found,
		)
	):
		return _STATE_UNKNOWN
	if connecting:
		return _STATE_CONNECTING
	if slave_flag or slave_session:
		return _STATE_SLAVE
	if master_flag or master_session:
		return _STATE_MASTER
	if connected:
		return _STATE_CONNECTED
	return _STATE_DISCONNECTED


class _RemoteBackend:
	"""Adaptateur minimal pour les implémentations distantes connues."""

	def __init__(self, name, owner, native=False):
		self.name = name
		self.owner = owner
		self.native = native

	def state(self):
		return _connection_state(self.owner)

	def disconnect(self):
		disconnect = _get_attribute(self.owner, "disconnect")
		if not callable(disconnect):
			return False
		if self.native:
			disconnect(_silent=True)
		else:
			disconnect()
		return True


def _is_native_remote_enabled():
	"""Lit la section [remote] déjà chargée par NVDA depuis nvda.ini."""
	try:
		return _as_bool(config.conf["remote"]["enabled"])
	except (AttributeError, KeyError, TypeError):
		return False


def _native_remote_backend():
	if not _is_native_remote_enabled():
		return None
	try:
		import _remoteClient
	except (ImportError, ModuleNotFoundError):
		return None
	client = _get_attribute(_remoteClient, "_remoteClient")
	if client is _MISSING or client is None:
		return None
	return _RemoteBackend("NVDA Remote", client, native=True)


def _plugin_identity(plugin):
	try:
		plugin_type = type(plugin)
		return ("%s.%s" % (plugin_type.__module__, plugin_type.__name__)).casefold()
	except (AttributeError, TypeError):
		return ""


def _is_supported_third_party_plugin(plugin):
	identity = _plugin_identity(plugin)
	return any(
		identifier in identity
		for identifier in _TELENVDA_IDENTIFIERS + _LEGACY_REMOTE_IDENTIFIERS
	)


def _remote_backends():
	backends = []
	native = _native_remote_backend()
	if native is not None:
		backends.append(native)
	try:
		running_plugins = tuple(globalPluginHandler.runningPlugins)
	except (AttributeError, TypeError):
		running_plugins = ()
	for plugin in running_plugins:
		if not _is_supported_third_party_plugin(plugin):
			continue
		if any(existing.owner is plugin for existing in backends):
			continue
		backends.append(_RemoteBackend(_plugin_identity(plugin), plugin))
	return backends


def _check_remote_backends(backends):
	if not backends:
		log.warning(
			"Aucun module d'accès distant compatible détecté ; la demande sera "
			"tout de même tentée."
		)
		return True
	for backend in backends:
		if backend.state() == _STATE_UNKNOWN:
			log.warning(
				"État du module d'accès distant %s inconnu ; la demande sera "
				"tout de même tentée.",
				backend.name,
			)
	return True


def _disconnect_active_backends(backends):
	active_backends = [
		backend for backend in backends if backend.state() in _ACTIVE_STATES
	]
	if not active_backends:
		return True
	if gui.messageBox(
		_(
			"Une connexion d'accès distant est déjà active. Voulez-vous la "
			"désactiver avant d'établir une nouvelle connexion esclave ?"
		),
		_("Assistance à distance Accessolutions"),
		wx.YES | wx.NO | wx.NO_DEFAULT | wx.ICON_WARNING,
	) != wx.YES:
		return False
	for backend in active_backends:
		try:
			if not backend.disconnect():
				raise RuntimeError("disconnect unavailable")
		except Exception:
			log.exception("Impossible de désactiver le module distant %s", backend.name)
			ui.message(_(
				"Impossible de désactiver la connexion d'accès distant. La "
				"nouvelle demande n'a pas été lancée."
			))
			return False
	for backend in backends:
		state = backend.state()
		if state in _ACTIVE_STATES:
			ui.message(_(
				"Impossible de désactiver la connexion d'accès distant. La "
				"nouvelle demande n'a pas été lancée."
			))
			return False
		if state == _STATE_UNKNOWN:
			log.warning(
				"État du module d'accès distant %s toujours inconnu après "
				"la demande de déconnexion ; la nouvelle demande sera tentée.",
				backend.name,
			)
	return True


def _ask_for_access_key():
	dialog = wx.Dialog(
		gui.mainFrame,
		title=_("Assistance à distance Accessolutions"),
	)
	sizer = wx.BoxSizer(wx.VERTICAL)
	label = wx.StaticText(
		dialog,
		label=_("Merci de saisir la clé d'accès du support Accessolutions :"),
	)
	sizer.Add(label, 0, wx.ALL, 10)
	key_control = wx.TextCtrl(
		dialog,
		size=(400, -1),
		style=wx.TE_PROCESS_ENTER,
	)
	key_control.SetName(_("Clé d'accès du support Accessolutions"))
	sizer.Add(key_control, 0, wx.LEFT | wx.RIGHT | wx.EXPAND, 10)

	button_sizer = wx.BoxSizer(wx.HORIZONTAL)
	cancel_button = wx.Button(dialog, wx.ID_CANCEL, _("Annuler"))
	ok_button = wx.Button(dialog, wx.ID_OK, _("OK"))
	button_sizer.Add(cancel_button, 0, wx.ALL, 5)
	button_sizer.Add(ok_button, 0, wx.ALL, 5)
	sizer.Add(button_sizer, 0, wx.ALIGN_RIGHT | wx.ALL, 5)

	def accept_key(event):
		if not key_control.GetValue().strip():
			ui.message(_("La clé d'accès est obligatoire."))
			key_control.SetFocus()
			return
		dialog.EndModal(wx.ID_OK)

	ok_button.Bind(wx.EVT_BUTTON, accept_key)
	key_control.Bind(wx.EVT_TEXT_ENTER, accept_key)
	cancel_button.Bind(wx.EVT_BUTTON, lambda event: dialog.EndModal(wx.ID_CANCEL))
	dialog.SetEscapeId(wx.ID_CANCEL)
	ok_button.SetDefault()
	dialog.SetSizerAndFit(sizer)
	key_control.SetFocus()

	gui.mainFrame.prePopup()
	try:
		with dialog:
			if dialog.ShowModal() != wx.ID_OK:
				return None
			return key_control.GetValue().strip()
	finally:
		gui.mainFrame.postPopup()


def _build_remote_url(access_key):
	query = urlencode({"mode": "slave", "key": access_key})
	return "%s?%s" % (REMOTE_ENDPOINT, query)


def runRemote():
	"""Demande la clé du support puis lance NVDA Remote."""
	backends = _remote_backends()
	if not _check_remote_backends(backends):
		return
	access_key = _ask_for_access_key()
	if not access_key:
		return
	# Relire l'état après la saisie afin de ne jamais remplacer une session
	# qui serait apparue pendant l'affichage de la boîte de dialogue.
	backends = _remote_backends()
	if not _check_remote_backends(backends):
		return
	if not _disconnect_active_backends(backends):
		return
	try:
		os.startfile(_build_remote_url(access_key))
	except (AttributeError, OSError) as error:
		log.exception("Impossible de lancer NVDA Remote")
		ui.message(_("Impossible de lancer NVDA Remote : %s") % error)
