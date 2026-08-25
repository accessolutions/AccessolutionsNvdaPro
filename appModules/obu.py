# *-* coding: utf8
# scripte pour OpenBook version 17 juin 2015
# (C) Accessolutions 2015

import speech
import appModuleHandler

class AppModule(appModuleHandler.AppModule):

	def event_appModule_gainFocus(self):
		speech.cancelSpeech()
		speech.setSpeechMode(speech.SpeechMode.off)
		
	def event_appModule_loseFocus(self):
		speech.setSpeechMode(speech.SpeechMode.talk)
