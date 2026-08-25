# *-* coding: utf8
# Script pour test des curseurs routing dans le bloc-note
# version 2019.07.18
# (C) Accessolutions 2015-2019

import api
import appModuleHandler
import inputCore
from logHandler import log
import scriptHandler
import speech


def handleGesture(gesture):
	focus = api.getFocusObject()
	if not focus:
		return
	# to avoid infinite recursive call
	saveAppModule = focus.appModule
	focus.appModule = None
	gesture.script = scriptHandler.findScript(gesture)
	# process the gesture
	if gesture.script:
		gesture.speechEffectWhenExecuted = None  # to suppress speech cancelation
		inputCore.manager.executeGesture(gesture)
	else:
		gesture.send()
	focus.appModule = saveAppModule


class AppModule(appModuleHandler.AppModule):
	scriptCategory = "notepad"
	
	speakRouting = False
	
	def getScript(self, gesture):
		try:
			identifier = gesture.normalizedIdentifiers[0]
			if identifier.startswith("br(") and identifier.endswith("routing"):
				return self.script_brailleRouting
		except:
			log.exception()
		return super(AppModule, self).getScript(gesture)
	
	def script_brailleRouting(self, gesture):
		if self.speakRouting:
			n = gesture.routingIndex + 1
			speech.speakMessage(repr(n))
		else:
			handleGesture(gesture)
	script_brailleRouting.__doc__ = u"Annonce du numéro de curseur routing"
	
	def script_basculeRouting(self, gesture):
		self.speakRouting = not self.speakRouting
		if self.speakRouting:
			speech.speakMessage (u"activation lecture des curseurs routing")
		else:
			speech.speakMessage (u"désactivation lecture des curseurs routing")
	script_basculeRouting.__doc__ = u"Active ou désactive la lecture du numéro de curseur routing"
	
	__gestures = {
		"kb:control+shift+r": "basculeRouting",
	}
