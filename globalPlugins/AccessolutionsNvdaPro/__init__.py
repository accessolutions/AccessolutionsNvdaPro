# *-* coding: utf8 *-*
# Version 2017.11.29

import globalPluginHandler
import os
import ui
from logHandler import log
import api
import speech
import wx
import gui
from . import remoteRequests
from . import updateAddon
import addonHandler
addonHandler.initTranslation()

class GlobalPlugin(globalPluginHandler.GlobalPlugin):
	scriptCategory = _("Accessolutions")

	def __init__ (self):
		super (GlobalPlugin, self).__init__()
		self.createMenu ()
		#updateAddon.autoUpdate ()

	def createMenu (self):
		self.accessolutionsMenu = wx.Menu()
		item = self.accessolutionsMenu.Append(wx.ID_ANY, u"&Assistance à distance", u"Effectue une ddemande d'assistance pour une prise de contrôle de l'ordinateur à distance par un technicien Accessolutions")
		gui.mainFrame.sysTrayIcon.Bind(wx.EVT_MENU , lambda evt: remoteRequests.runRemote (), item)
		self.submenu_item = gui.mainFrame.sysTrayIcon.menu.InsertMenu(2, wx.ID_ANY, "&Accessolutions", self.accessolutionsMenu)

	def removeMenu(self):
		if self.submenu_item is not None:
			try:
				gui.mainFrame.sysTrayIcon.menu.RemoveItem(self.submenu_item)
			except:
				pass
			self.submenu_item.Destroy()

	def  terminate(self):
		try:
			self.removeMenu()
		except:
			pass

	def script_runRemote(self, gesture):
		wx.CallAfter (remoteRequests.runRemote)
	script_runRemote.__doc__ = _(u"Demande d'assistance à distance Accessolutions")
		
	__gestures = {
		"kb:windows+control+r" : "runRemote",
	}
