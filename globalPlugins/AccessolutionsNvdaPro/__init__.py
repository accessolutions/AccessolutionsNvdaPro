import globalPluginHandler
import os
import ui
from logHandler import log
import api
import inputCore
import config
import core
import speech
import queueHandler
import wx
import gui
import globalVars
from . import remoteRequests
from . import updater
import addonHandler
addonHandler.initTranslation()

confSpecs = {
	"useFrenchNavGestures": "boolean(default=true)",
	"checkForUpdatesAtStartup": "boolean(default=true)",
}
config.conf.spec["AccessolutionsNVDAPro"] = confSpecs

def loadNavGestures():
	inputCore.manager.localeGestureMap.load(
		os.path.abspath(os.path.join(
			os.path.dirname(__file__), "gestures.ini")
		)
	)

class SettingsDlg(gui.settingsDialogs.SettingsPanel):

	title = "AccessolutionsNVDAPro"

	def makeSettings(self, settingsSizer):
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
		self.restartRequired = False
		self.oldVal = config.conf["AccessolutionsNVDAPro"]["useFrenchNavGestures"]
		self.newVal = self.useFrenchNavGestures.GetValue()
		config.conf["AccessolutionsNVDAPro"]["useFrenchNavGestures"] = self.newVal
		config.conf["AccessolutionsNVDAPro"]["checkForUpdatesAtStartup"] = self.checkForUpdatesAtStartup.GetValue()
		if self.newVal == self.oldVal:
			return
		self.restartRequired = not self.newVal

	def postSave(self):
		if self.newVal:
			loadNavGestures()
		if self.restartRequired:
			res = gui.messageBox(
				_("Vous devez redémarrer NVDA pour que les changements prennent effet. Voulez-vous redémarrer maintenant?"),
				_("AccessolutionsNVDAPro"),
				style=wx.YES_NO | wx.ICON_QUESTION
			)
			if res == wx.YES:
				queueHandler.queueFunction(queueHandler.eventQueue,core.restart)


class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	scriptCategory = _("Accessolutions")

	def __init__(self):
		super(GlobalPlugin, self).__init__()
		self.update_manager = updater.UpdateManager()
		self._startup_update_checked = False
		self._terminated = False
		self._startup_update_registered = False
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
			wx.CallLater(10000, self.postStartupHandler)

	def createMenu(self):
		self.accessolutionsMenu = wx.Menu()
		item = self.accessolutionsMenu.Append(
			wx.ID_ANY,
			"&Assistance à distance",
			"Effectue une ddemande d'assistance pour une prise de contrôle de l'ordinateur à distance par un technicien Accessolutions"
		)
		gui.mainFrame.sysTrayIcon.Bind(
			wx.EVT_MENU,
			lambda evt: remoteRequests.runRemote(),
			item
		)
		self.update_item = self.accessolutionsMenu.Append(
			wx.ID_ANY,
			_("Vérifier les mises à jour..."),
			_("Rechercher une nouvelle version d'Accessolutions NVDA Pro")
		)
		gui.mainFrame.sysTrayIcon.Bind(
			wx.EVT_MENU,
			lambda evt: self._start_update_check(manual=True),
			self.update_item
		)
		self.submenu_item = gui.mainFrame.sysTrayIcon.menu.InsertMenu(
			2,
			wx.ID_ANY,
			"&Accessolutions",
			self.accessolutionsMenu
		)

	def removeMenu(self):
		if self._startup_update_registered:
			try:
				core.postNvdaStartup.unregister(self.postStartupHandler)
			except (AttributeError, ValueError):
				pass
			self._startup_update_registered = False
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(
			SettingsDlg
		)
		if self.submenu_item is not None:
			gui.mainFrame.sysTrayIcon.menu.RemoveItem(self.submenu_item)
			self.submenu_item.Destroy()

	def terminate(self):
		self._terminated = True
		self.update_manager.terminate()
		self.removeMenu()

	def postStartupHandler(self):
		if self._terminated or self._startup_update_checked:
			return
		self._startup_update_checked = True
		if getattr(globalVars.appArgs, "secure", False):
			return
		if not config.conf["AccessolutionsNVDAPro"]["checkForUpdatesAtStartup"]:
			return
		# Let NVDA finish loading its add-ons and its GUI before starting network I/O.
		wx.CallLater(5000, self._start_update_check, False)

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
		if not self.update_manager.download_async(update, self._on_update_download_finished):
			self.update_item.Enable(True)
			gui.messageBox(
				_("Une autre opération de mise à jour est déjà en cours."),
				_("Mise à jour d'Accessolutions NVDA Pro"),
				wx.OK | wx.ICON_INFORMATION,
			)

	def _on_update_download_finished(self, path, error):
		wx.CallAfter(self._handle_update_download_finished, path, error)

	def _handle_update_download_finished(self, path, error):
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
			updater.install_package(path)
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

	def script_runRemote(self, gesture):
		wx.CallAfter(remoteRequests.runRemote)
	script_runRemote.__doc__ = _("Demande d'assistance à distance Accessolutions")

	__gestures = {
		"kb:windows+control+r": "runRemote",
	}
