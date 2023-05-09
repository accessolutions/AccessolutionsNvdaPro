# *-* coding: utf8 *-*
# Installation de Accessolutions NVDA Pro 
# Version 2016.09.02

import globalPluginHandler
import ui
from logHandler import log
import os
import globalVars
import config
import wx
import installer
import gui


class InstallerDialog(wx.Dialog):

	def __init__(self, parent, isUpdate):
		self.isUpdate=isUpdate
		# Translators: The title of the Install NVDA dialog.
		super(InstallerDialog, self).__init__(parent, title=_("Installation de Accessolutions NVDA Pro"))
		mainSizer = self.mainSizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: An informational message in the Install NVDA dialog.
		msg=_("To install NVDA to your hard drive, please press the Continue button.")
		if self.isUpdate:
			# Translators: An informational message in the Install NVDA dialog.
			msg+=" "+_("A previous copy of NVDA has been found on your system. This copy will be updated.") 
			if not os.path.isdir(installer.defaultInstallPath):
				# Translators: a message in the installer telling the user NVDA is now located in a different place.
				msg+=" "+_("The installation path for NVDA has changed. it will now  be installed in {path}").format(path=installer.defaultInstallPath)
		dialogCaption=wx.StaticText(self,label=msg) 
		mainSizer.Add(dialogCaption)
		optionsSizer = wx.BoxSizer(wx.VERTICAL)
		# Translators: The label of a checkbox option in the Install NVDA dialog.
		ctrl = self.startOnLogonCheckbox = wx.CheckBox(self, label=_("Use NVDA on the Windows &logon screen"))
		ctrl.Value = config.getStartOnLogonScreen() if self.isUpdate else True
		optionsSizer.Add(ctrl)
		shortcutIsPrevInstalled=installer.isDesktopShortcutInstalled()
		if self.isUpdate and shortcutIsPrevInstalled:
			# Translators: The label of a checkbox option in the Install NVDA dialog.
			ctrl = self.createDesktopShortcutCheckbox = wx.CheckBox(self, label=_("&Keep existing desktop shortcut"))
		else:
			# Translators: The label of the option to create a desktop shortcut in the Install NVDA dialog.
			# If the shortcut key has been changed for this locale,
			# this change must also be reflected here.
			ctrl = self.createDesktopShortcutCheckbox = wx.CheckBox(self, label=_("Create &desktop icon and shortcut key (control+alt+n)"))
		ctrl.Value = shortcutIsPrevInstalled if self.isUpdate else True 
		optionsSizer.Add(ctrl)
		# Translators: The label of a checkbox option in the Install NVDA dialog.
		ctrl = self.copyPortableConfigCheckbox = wx.CheckBox(self, label=_("Copy &portable configuration to current user account"))
		ctrl.Value = True
		if globalVars.appArgs.launcher:
			ctrl.Disable()
		optionsSizer.Add(ctrl)
		mainSizer.Add(optionsSizer)

		sizer = wx.BoxSizer(wx.HORIZONTAL)
		# Translators: The label of a button to continue with the operation.
		ctrl = wx.Button(self, label=_("&Continue"), id=wx.ID_OK)
		ctrl.SetDefault()
		ctrl.Bind(wx.EVT_BUTTON, self.onInstall)
		sizer.Add(ctrl)
		sizer.Add(wx.Button(self, id=wx.ID_CANCEL))
		# If we bind this using button.Bind, it fails to trigger when the dialog is closed.
		self.Bind(wx.EVT_BUTTON, self.onCancel, id=wx.ID_CANCEL)
		mainSizer.Add(sizer)

		self.Sizer = mainSizer
		mainSizer.Fit(self)
		self.Center(wx.BOTH | wx.CENTER_ON_SCREEN)

	def onInstall(self, evt):
		self.Hide()
		import gui.installerGui
		gui.installerGui.doInstall(self.createDesktopShortcutCheckbox.Value,self.startOnLogonCheckbox.Value,self.copyPortableConfigCheckbox.Value,self.isUpdate)
		self.Destroy()

	def onCancel(self, evt):
		self.Destroy()

def showInstallGui():
	gui.mainFrame.prePopup()
	previous = installer.comparePreviousInstall()
	if previous > 0:
		# The existing installation is newer, which means this will be a downgrade.
		# Translators: The title of a warning dialog.
		d = wx.Dialog(gui.mainFrame, title=_("Warning"))
		mainSizer = wx.BoxSizer(wx.VERTICAL)
		item = wx.StaticText(d,
			# Translators: A warning presented when the user attempts to downgrade NVDA
			# to an older version.
			label=_("You are attempting to install an earlier version of NVDA than the version currently installed. "
			"If you really wish to revert to an earlier version, you should first cancel this installation and completely uninstall NVDA before installing the earlier version."))
		mainSizer.Add(item)
		sizer = wx.BoxSizer(wx.HORIZONTAL)
		item = wx.Button(d, id=wx.ID_OK,
			# Translators: The label of a button to proceed with installation,
			# even though this is not recommended.
			label=_("&Proceed with installation (not recommended)"))
		sizer.Add(item)
		item = wx.Button(d, id=wx.ID_CANCEL)
		sizer.Add(item)
		item.SetFocus()
		mainSizer.Add(sizer)
		d.Sizer = mainSizer
		mainSizer.Fit(d)
		d.Center(wx.BOTH | wx.CENTER_ON_SCREEN)
		with d:
			if d.ShowModal() == wx.ID_CANCEL:
				gui.mainFrame.postPopup()
				return
	InstallerDialog(gui.mainFrame, previous is not None).Show()
	gui.mainFrame.postPopup()

class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	def __init__ (self):
		super(globalPluginHandler.GlobalPlugin, self).__init__()
		if r"AccessoNVDAProInstaller" in __file__:
			self.installAccessoNVDAPro ()

	def installAccessoNVDAPro (self):
		import tones
		showInstallGui ()
		tones.beep (1000, 50)

	def script_shortcutInst (self, gesture):
		self.installAccessoNVDAPro ()

	__gestures = {
		"kb:windows+control+i" : "shortcutInst",
	}
