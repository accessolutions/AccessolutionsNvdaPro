# *-* coding: utf8 *-*
# Permet l'utilisation de NVDA+f7 en mode formulaire 
# version du 27 août 2015

import globalPluginHandler
import ui
import api
import scriptHandler

class GlobalPlugin(globalPluginHandler.GlobalPlugin):

	def script_manageNVDAF7 (self, gesture):
		# Tree interceptor level.
		focus = api.getFocusObject()
		if focus is None:
			return
		treeInterceptor = focus.treeInterceptor
		if treeInterceptor and treeInterceptor.isReady:
			func = treeInterceptor.getScript(gesture)
			if func:
				func(gesture)
				return
		ui.message (u"pas de lien")

	__gestures = {
		"kb:NVDA+f7" : "manageNVDAF7",
	}
