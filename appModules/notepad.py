# -*- coding: utf-8 -*-
# Script pour test des curseurs routing dans le bloc-note
# version 2019.07.18
# (C) Accessolutions 2015-2019

import api
import appModuleHandler
import inputCore
from logHandler import log
import scriptHandler
import speech
import addonHandler

addonHandler.initTranslation()


def handleGesture(gesture):
	focus = api.getFocusObject()
	if not focus:
		return
	# to avoid infinite recursive call
	saveAppModule = focus.appModule
	try:
		focus.appModule = None
		gesture.script = scriptHandler.findScript(gesture)
		# process the gesture
		if gesture.script:
			gesture.speechEffectWhenExecuted = None  # to suppress speech cancelation
			inputCore.manager.executeGesture(gesture)
		else:
			gesture.send()
	finally:
		# Always restore the app module, including when gesture processing fails.
		focus.appModule = saveAppModule


class AppModule(appModuleHandler.AppModule):
	scriptCategory = _("Bloc-notes")
	
	speakRouting = False
	
	def getScript(self, gesture):
		try:
			identifier = gesture.normalizedIdentifiers[0]
			if identifier.startswith("br(") and identifier.endswith("routing"):
				return self.script_brailleRouting
		except (AttributeError, IndexError, TypeError):
			log.exception(_("Impossible d’inspecter le geste du Bloc-notes"))
		return super(AppModule, self).getScript(gesture)
	
	def script_brailleRouting(self, gesture):
		if self.speakRouting:
			n = gesture.routingIndex + 1
			speech.speakMessage(repr(n))
		else:
			handleGesture(gesture)
	script_brailleRouting.__doc__ = _("Annonce du numéro de curseur de routage")
	
	def script_basculeRouting(self, gesture):
		self.speakRouting = not self.speakRouting
		if self.speakRouting:
			speech.speakMessage (_("Lecture des curseurs de routage activée"))
		else:
			speech.speakMessage (_("Lecture des curseurs de routage désactivée"))
	script_basculeRouting.__doc__ = _("Active ou désactive la lecture du numéro de curseur de routage")
	
	__gestures = {
		"kb:control+shift+r": "basculeRouting",
	}
