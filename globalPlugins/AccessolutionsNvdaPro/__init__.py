# -*- coding: utf-8 -*-

import globalPluginHandler
import os
import ui
import webbrowser
from logHandler import log
import api
import inputCore
import config
import core
import speech
import wx
import gui
import globalVars
from . import remoteRequests
from . import updater
import addonHandler
from scriptHandler import script
addonHandler.initTranslation()

ACCESSOLUTIONS_WEBSITE = "https://accessolutions.fr"

confSpecs = {
	"useFrenchNavGestures": "boolean(default=true)",
	"checkForUpdatesAtStartup": "boolean(default=true)",
}
config.conf.spec["AccessolutionsNVDAPro"] = confSpecs


# Associations ajoutées par gestures.ini. Elles sont retirées avant chaque
# chargement afin d'éviter les doublons dans la carte globale de NVDA.
_NAV_GESTURE_MAPPINGS = (
	("cursorManager", "CursorManager", "findPrevious", "kb:shift+f3"),
	("cursorManager", "CursorManager", "find", "kb:control+f"),
	("cursorManager", "CursorManager", "findNext", "kb:f3"),
	("browseMode", "BrowseModeTreeInterceptor", "refreshBuffer", "kb:nvda+escape"),
	("browseMode", "BrowseModeTreeInterceptor", "moveToStartOfContainer", "kb:q+shift"),
	("browseMode", "BrowseModeTreeInterceptor", "previousTable", "kb:y+shift"),
	("browseMode", "BrowseModeTreeInterceptor", "previousHeading", "kb:shift+t"),
	("browseMode", "BrowseModeTreeInterceptor", "previousButton", "kb:shift+u"),
	("browseMode", "BrowseModeTreeInterceptor", "previousComboBox", "kb:shift+z"),
	("browseMode", "BrowseModeTreeInterceptor", "previousNotLinkBlock", "kb:shift+b"),
	("browseMode", "BrowseModeTreeInterceptor", "previousBlockQuote", "kb:shift+c"),
	("browseMode", "BrowseModeTreeInterceptor", "previousFrame", "kb:shift+h"),
	("browseMode", "BrowseModeTreeInterceptor", "previousUnvisitedLink", "kb:shift+n"),
	("browseMode", "BrowseModeTreeInterceptor", "nextTable", "kb:y"),
	("browseMode", "BrowseModeTreeInterceptor", "nextComboBox", "kb:z"),
	("browseMode", "BrowseModeTreeInterceptor", "nextButton", "kb:u"),
	("browseMode", "BrowseModeTreeInterceptor", "nextHeading", "kb:t"),
	("browseMode", "BrowseModeTreeInterceptor", "movePastEndOfContainer", "kb:q"),
	("browseMode", "BrowseModeTreeInterceptor", "nextUnvisitedLink", "kb:n"),
	("browseMode", "BrowseModeTreeInterceptor", "nextFrame", "kb:h"),
	("browseMode", "BrowseModeTreeInterceptor", "nextBlockQuote", "kb:c"),
	("browseMode", "BrowseModeTreeInterceptor", "nextNotLinkBlock", "kb:b"),
)


def _navGesturesPath():
	return os.path.abspath(os.path.join(
		os.path.dirname(__file__), "gestures.ini"
	))


def unloadNavGestures():
	"""Retire toutes les associations de navigation de cette extension."""
	gestureMap = inputCore.manager.localeGestureMap
	for moduleName, className, scriptName, gesture in _NAV_GESTURE_MAPPINGS:
		while True:
			try:
				gestureMap.remove(gesture, moduleName, className, scriptName)
			except ValueError:
				break


def loadNavGestures():
	unloadNavGestures()
	inputCore.manager.localeGestureMap.load(_navGesturesPath())

class SettingsDlg(gui.settingsDialogs.SettingsPanel):

	title = _("AccessolutionsNVDAPro")

	def makeSettings(self, settingsSizer):
		self._saveCompleted = False
		self.newVal = None
		sHelper = gui.guiHelper.BoxSizerHelper(self, sizer=settingsSizer)
		self.useFrenchNavGestures = sHelper.addItem(wx.CheckBox(
			self,
			label=_("En mode navigation, utiliser des raccourcis similaires à JAWS"))
		)
		self.useFrenchNavGestures.SetValue(
			config.conf["AccessolutionsNVDAPro"]["useFrenchNavGestures"]
		)
		self.checkForUpdatesAtStartup = sHelper.addItem(wx.CheckBox(
			self,
			label=_("Rechercher automatiquement les mises à jour au démarrage de NVDA")
		))
		self.checkForUpdatesAtStartup.SetValue(
			config.conf["AccessolutionsNVDAPro"]["checkForUpdatesAtStartup"]
		)

	def onSave(self):
		self._saveCompleted = False
		self.oldVal = config.conf["AccessolutionsNVDAPro"]["useFrenchNavGestures"]
		self.newVal = self.useFrenchNavGestures.GetValue()
		config.conf["AccessolutionsNVDAPro"]["useFrenchNavGestures"] = self.newVal
		config.conf["AccessolutionsNVDAPro"]["checkForUpdatesAtStartup"] = self.checkForUpdatesAtStartup.GetValue()
		if self.newVal == self.oldVal:
			self._saveCompleted = True
			return
		self._saveCompleted = True

	def postSave(self):
		if not getattr(self, "_saveCompleted", False):
			return
		self._saveCompleted = False
		if self.newVal:
			loadNavGestures()
		else:
			unloadNavGestures()


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	scriptCategory = _("Accessolutions")

	def __init__(self):
		super(GlobalPlugin, self).__init__()
		self.update_manager = updater.UpdateManager()
		self._startup_update_checked = False
		self._terminated = False
		self._startup_update_registered = False
		self._startup_fallback_timer = None
		self._startup_update_timer = None
		self.remote_item = None
		self.website_item = None
		self.update_item = None
		self.submenu_item = None
		self._remote_menu_handler = None
		self._website_menu_handler = None
		self._update_menu_handler = None
		self.createMenu()
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(
			SettingsDlg
		)
		if config.conf["AccessolutionsNVDAPro"]["useFrenchNavGestures"]:
			loadNavGestures()
		try:
			core.postNvdaStartup.register(self.postStartupHandler)
			self._startup_update_registered = True
		except AttributeError:
			# Fallback for NVDA versions without the post-startup extension point.
			self._startup_fallback_timer = wx.CallLater(10000, self.postStartupHandler)

	def createMenu(self):
		self.accessolutionsMenu = wx.Menu()
		self.remote_item = self.accessolutionsMenu.Append(
			wx.ID_ANY,
			_("&Assistance à distance"),
			_("Effectue une demande d'assistance pour une prise de contrôle de l'ordinateur à distance par un technicien Accessolutions")
		)
		self._remote_menu_handler = self._on_remote_menu
		gui.mainFrame.sysTrayIcon.Bind(
			wx.EVT_MENU,
			self._remote_menu_handler,
			self.remote_item
		)
		self.website_item = self.accessolutionsMenu.Append(
			wx.ID_ANY,
			_("Produits et services pour personnes déficientes visuelles - Accessolutions"),
			_("Ouvre le site Accessolutions dans le navigateur par défaut"),
		)
		self._website_menu_handler = self._on_website_menu
		gui.mainFrame.sysTrayIcon.Bind(
			wx.EVT_MENU,
			self._website_menu_handler,
			self.website_item,
		)
		self.update_item = self.accessolutionsMenu.Append(
			wx.ID_ANY,
			_("Vérifier les mises à jour..."),
			_("Rechercher une nouvelle version d'Accessolutions NVDA Pro")
		)
		self._update_menu_handler = self._on_update_menu
		gui.mainFrame.sysTrayIcon.Bind(
			wx.EVT_MENU,
			self._update_menu_handler,
			self.update_item,
		)
		self.submenu_item = gui.mainFrame.sysTrayIcon.menu.InsertMenu(
			2,
			wx.ID_ANY,
			_("&Accessolutions"),
			self.accessolutionsMenu
		)

	def _on_remote_menu(self, event):
		if not self._terminated:
			remoteRequests.runRemote()

	def _on_update_menu(self, event):
		if not self._terminated:
			self._start_update_check(manual=True)

	def _on_website_menu(self, event):
		if self._terminated:
			return
		try:
			if not webbrowser.open(ACCESSOLUTIONS_WEBSITE, new=2):
				raise webbrowser.Error("Le navigateur par défaut n'a pas été lancé")
		except (OSError, webbrowser.Error):
			log.exception("Impossible d'ouvrir le site Accessolutions")
			ui.message(_("Impossible d'ouvrir le site Accessolutions dans le navigateur par défaut."))

	def removeMenu(self):
		self._stop_timer("_startup_fallback_timer")
		self._stop_timer("_startup_update_timer")
		if self._startup_update_registered:
			try:
				core.postNvdaStartup.unregister(self.postStartupHandler)
			except (AttributeError, ValueError):
				pass
			self._startup_update_registered = False
		try:
			gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(SettingsDlg)
		except ValueError:
			pass
		tray = getattr(gui.mainFrame, "sysTrayIcon", None)
		if tray is not None:
			for item, handler in (
				(self.remote_item, self._remote_menu_handler),
				(self.website_item, self._website_menu_handler),
				(self.update_item, self._update_menu_handler),
			):
				if item is None or handler is None:
					continue
				try:
					tray.Unbind(wx.EVT_MENU, handler=handler, source=item)
				except (AttributeError, TypeError):
					pass
		if self.submenu_item is not None:
			if tray is not None:
				try:
					tray.menu.RemoveItem(self.submenu_item)
				except (AttributeError, RuntimeError):
					pass
			try:
				self.submenu_item.Destroy()
			except (AttributeError, RuntimeError):
				pass
			self.submenu_item = None
		self.remote_item = None
		self.website_item = None
		self.update_item = None
		self._remote_menu_handler = None
		self._website_menu_handler = None
		self._update_menu_handler = None

	def _stop_timer(self, attribute):
		timer = getattr(self, attribute, None)
		if timer is None:
			return
		try:
			timer.Stop()
		except (AttributeError, RuntimeError):
			pass
		setattr(self, attribute, None)

	def terminate(self):
		if self._terminated:
			return
		self._terminated = True
		self._stop_timer("_startup_fallback_timer")
		self._stop_timer("_startup_update_timer")
		self.update_manager.terminate()
		self.removeMenu()
		unloadNavGestures()
		super(GlobalPlugin, self).terminate()

	def postStartupHandler(self):
		self._startup_fallback_timer = None
		if self._terminated or self._startup_update_checked:
			return
		self._startup_update_checked = True
		if getattr(globalVars.appArgs, "secure", False):
			return
		if not config.conf["AccessolutionsNVDAPro"]["checkForUpdatesAtStartup"]:
			return
		# Let NVDA finish loading its add-ons and its GUI before starting network I/O.
		self._startup_update_timer = wx.CallLater(
			5000, self._run_startup_update_check
		)

	def _run_startup_update_check(self):
		self._startup_update_timer = None
		self._start_update_check(manual=False)

	def _current_addon_version(self):
		try:
			return str(addonHandler.getCodeAddon().manifest["version"])
		except (addonHandler.AddonError, AttributeError, KeyError):
			return "0.0.0"

	def _start_update_check(self, manual=False):
		if self._terminated:
			return
		started = self.update_manager.check_async(
			current_version=self._current_addon_version(),
			callback=self._on_update_check_finished,
			manual=manual,
		)
		if started:
			self.update_item.Enable(False)
		elif manual:
			gui.messageBox(
				_("Une vérification des mises à jour est déjà en cours."),
				_("Mise à jour d'Accessolutions NVDA Pro"),
				wx.OK | wx.ICON_INFORMATION,
			)

	def _on_update_check_finished(self, update, error, manual):
		wx.CallAfter(self._handle_update_check_finished, update, error, manual)

	def _handle_update_check_finished(self, update, error, manual):
		if self._terminated:
			return
		self.update_item.Enable(True)
		if error:
			if manual:
				gui.messageBox(
					_("Impossible de rechercher les mises à jour.\n\n{error}").format(error=error),
					_("Mise à jour d'Accessolutions NVDA Pro"),
					wx.OK | wx.ICON_ERROR,
				)
			return
		if update is None:
			if manual:
				gui.messageBox(
					_("Accessolutions NVDA Pro est à jour."),
					_("Mise à jour d'Accessolutions NVDA Pro"),
					wx.OK | wx.ICON_INFORMATION,
				)
			return
		message = _(
			"Une mise à jour d'Accessolutions NVDA Pro est disponible : version {version}.\n\n"
			"Voulez-vous la télécharger et l'installer maintenant ?"
		).format(version=update.version)
		if gui.messageBox(
			message,
			_("Mise à jour d'Accessolutions NVDA Pro"),
			wx.YES | wx.NO | wx.ICON_INFORMATION,
		) != wx.YES:
			return
		self.update_item.Enable(False)
		if not self.update_manager.download_async(
			update,
			lambda path, error: self._on_update_download_finished(update, path, error),
		):
			self.update_item.Enable(True)
			gui.messageBox(
				_("Une autre opération de mise à jour est déjà en cours."),
				_("Mise à jour d'Accessolutions NVDA Pro"),
				wx.OK | wx.ICON_INFORMATION,
			)

	def _on_update_download_finished(self, update, path, error):
		wx.CallAfter(self._handle_update_download_finished, update, path, error)

	def _handle_update_download_finished(self, update, path, error):
		if self._terminated:
			if path:
				updater.remove_temporary_file(path)
			return
		self.update_item.Enable(True)
		if error:
			gui.messageBox(
				_("Impossible de télécharger ou de vérifier la mise à jour.\n\n{error}").format(error=error),
				_("Mise à jour d'Accessolutions NVDA Pro"),
				wx.OK | wx.ICON_ERROR,
			)
			return
		try:
			updater.install_package(path, expected_version=update.version)
		except Exception as error:
			gui.messageBox(
				_("NVDA n'a pas pu installer la mise à jour.\n\n{error}").format(error=error),
				_("Mise à jour d'Accessolutions NVDA Pro"),
				wx.OK | wx.ICON_ERROR,
			)
		else:
			if gui.messageBox(
				_("La mise à jour est installée. NVDA doit être redémarré pour terminer l'installation. Redémarrer maintenant ?"),
				_("Mise à jour d'Accessolutions NVDA Pro"),
				wx.YES | wx.NO | wx.ICON_INFORMATION,
			) == wx.YES:
				core.restart()
		finally:
			if path:
				updater.remove_temporary_file(path)

	@script(
		description=_("Demande une assistance à distance Accessolutions"),
		gesture="kb:windows+control+r",
	)
	def script_runRemote(self, gesture):
		wx.CallAfter(remoteRequests.runRemote)
