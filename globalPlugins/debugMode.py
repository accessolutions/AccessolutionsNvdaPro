# *-* coding: utf8 *-*
# activation et désactivation du mode debug 
# Version 2017.11.29

import globalPluginHandler
import ui
import versionInfo

class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	def script_debugMode (self, gesture):
		versionInfo.isTestVersion = not versionInfo.isTestVersion
		if versionInfo.isTestVersion :
			ui.message ("mode debug")
		else:
			ui.message ("mode normal")

	__gestures = {
		"kb:windows+control+shift+d" : "debugMode",
	}
