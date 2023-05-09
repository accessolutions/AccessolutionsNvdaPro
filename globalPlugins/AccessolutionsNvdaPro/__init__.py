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
from . import remoteRequests
from . import updateAddon
import addonHandler
addonHandler.initTranslation()

confSpecs = {
	"useFrenchNavGestures": "boolean(default=true)"
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

	def onSave(self):
		self.restartRequired = False
		self.oldVal = config.conf["AccessolutionsNVDAPro"]["useFrenchNavGestures"]
		self.newVal = self.useFrenchNavGestures.GetValue()
		config.conf["AccessolutionsNVDAPro"]["useFrenchNavGestures"] = self.newVal
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
		self.createMenu()
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.append(
			SettingsDlg
		)
		if config.conf["AccessolutionsNVDAPro"]["useFrenchNavGestures"]:
			loadNavGestures()
		# updateAddon.autoUpdate ()

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
		self.submenu_item = gui.mainFrame.sysTrayIcon.menu.InsertMenu(
			2,
			wx.ID_ANY,
			"&Accessolutions",
			self.accessolutionsMenu
		)

	def removeMenu(self):
		gui.settingsDialogs.NVDASettingsDialog.categoryClasses.remove(
			SettingsDlg
		)
		if self.submenu_item is not None:
			gui.mainFrame.sysTrayIcon.menu.RemoveItem(self.submenu_item)
			self.submenu_item.Destroy()

	def terminate(self):
		self.removeMenu()

	def script_runRemote(self, gesture):
		wx.CallAfter(remoteRequests.runRemote)
	script_runRemote.__doc__ = _("Demande d'assistance à distance Accessolutions")

	__gestures = {
		"kb:windows+control+r": "runRemote",
	}
